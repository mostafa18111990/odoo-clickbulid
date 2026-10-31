#!/bin/bash
# Production activation for NEW Odoo 20 tenants only.
# Existing Odoo 19 databases, containers, and tenant nginx blocks remain intact.
set -Eeuo pipefail
umask 077

RELEASE_ARCHIVE=${1:-}
RELEASE_SHA=${2:-}
PLATFORM_ROOT=${PLATFORM_ROOT:-/opt/odoo-saas}
RELEASES_ROOT=${RELEASES_ROOT:-/opt/odoo20-releases}
BACKUP_ROOT=${BACKUP_ROOT:-$PLATFORM_ROOT/backups}
PG19_CONTAINER=${PG19_CONTAINER:-odoo_saas_postgres}
ODOO19_CONTAINER=${ODOO19_CONTAINER:-odoo_saas_app}
ODOO19_ENTERPRISE_CONTAINER=${ODOO19_ENTERPRISE_CONTAINER:-odoo_saas_ent}
NGINX_CONTAINER=${NGINX_CONTAINER:-odoo_saas_nginx}
ODOO20_COMPOSE_PROJECT=${ODOO20_COMPOSE_PROJECT:-clickbuild-odoo20-tenants}
ENTERPRISE20_PATH=${ODOO20_ENTERPRISE_PATH:-$PLATFORM_ROOT/enterprise20}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$BACKUP_ROOT/pre-odoo20-$STAMP"
RELEASE_DIR="$RELEASES_ROOT/${RELEASE_SHA:-$STAMP}"
CURRENT_LINK="$RELEASES_ROOT/current"
LOCK_FILE=/run/lock/clickbuild-odoo20-activation.lock
ACTIVATION_STARTED=0
SCRATCH_DB="cb20restore${STAMP//[^0-9]/}"
PREVIOUS_RELEASE=''
ODOO19_VERSION=''
TENANT_CONFIG_CHECKSUM=''

fail() { printf 'FAIL: %s\n' "$*" >&2; return 1; }
need_container() { docker inspect "$1" >/dev/null 2>&1 || fail "missing container: $1"; }
container_healthy() {
    local state
    state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1")
    [ "$state" = healthy ] || [ "$state" = running ] || fail "$1 is not healthy (state=$state)"
}
wait_container_healthy() {
    local container=$1 state deadline
    deadline=$((SECONDS + 180))
    while [ "$SECONDS" -lt "$deadline" ]; do
        state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
        case "$state" in
            healthy|running) return 0 ;;
            unhealthy|exited|dead) fail "$container failed while waiting for health (state=$state)" ;;
        esac
        sleep 3
    done
    fail "$container did not become healthy within 180 seconds (state=$state)"
}

rollback() {
    local rc=$?
    trap - ERR
    if [ "$ACTIVATION_STARTED" -eq 1 ]; then
        printf 'Activation failed; restoring host routing and provisioner files from %s\n' "$BACKUP_DIR" >&2
        [ ! -f "$BACKUP_DIR/host/config/nginx.conf" ] || install -m 640 "$BACKUP_DIR/host/config/nginx.conf" "$PLATFORM_ROOT/config/nginx.conf"
        [ ! -f "$BACKUP_DIR/host/saas-tenant-provisioner.sh" ] || install -m 755 "$BACKUP_DIR/host/saas-tenant-provisioner.sh" /usr/local/bin/saas-tenant-provisioner.sh
        [ ! -f "$BACKUP_DIR/host/saas-cert-sweeper.sh" ] || install -m 755 "$BACKUP_DIR/host/saas-cert-sweeper.sh" /usr/local/bin/saas-cert-sweeper.sh
        [ ! -f "$BACKUP_DIR/host/provision_tenant_cert.sh" ] || install -m 755 "$BACKUP_DIR/host/provision_tenant_cert.sh" "$PLATFORM_ROOT/provision_tenant_cert.sh"
        if [ -n "$PREVIOUS_RELEASE" ] && [ -f "$PREVIOUS_RELEASE/docker/odoo20/docker-compose.tenants.yml" ]; then
            export ODOO20_ENTERPRISE_PATH="$ENTERPRISE20_PATH"
            docker compose -p "$ODOO20_COMPOSE_PROJECT" \
                -f "$PREVIOUS_RELEASE/docker/odoo20/docker-compose.tenants.yml" \
                --env-file "$PREVIOUS_RELEASE/docker/odoo20/.env" up -d --build
            ln -sfn "$PREVIOUS_RELEASE" "$CURRENT_LINK"
        fi
        docker exec "$NGINX_CONTAINER" nginx -t
        docker exec "$NGINX_CONTAINER" nginx -s reload
        systemctl restart saas-cert-sweeper.timer
    fi
    docker exec "$PG19_CONTAINER" dropdb -U odoo --if-exists --force "$SCRATCH_DB" >/dev/null 2>&1 || :
    exit "$rc"
}
trap rollback ERR

[ "$(id -u)" -eq 0 ] || fail 'run as root'
[ -n "$RELEASE_ARCHIVE" ] && [ -f "$RELEASE_ARCHIVE" ] || fail 'release archive is required'
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'release SHA must be a 40-character commit id'
exec 9>"$LOCK_FILE"
flock -n 9 || fail 'another activation is running'

for container in "$PG19_CONTAINER" "$ODOO19_CONTAINER" "$NGINX_CONTAINER" odoo_saas_postgres20 odoo_saas_20_community odoo_saas_20_enterprise; do
    need_container "$container"
done
container_healthy odoo_saas_postgres20
container_healthy odoo_saas_20_community
container_healthy odoo_saas_20_enterprise
ODOO19_VERSION=$(docker exec "$ODOO19_CONTAINER" odoo --version)
printf '%s\n' "$ODOO19_VERSION" | grep -q 'Odoo Server 19'
docker exec odoo_saas_20_community odoo --version | grep -q 'Odoo Server 20'
docker exec odoo_saas_20_enterprise odoo --version | grep -q 'Odoo Server 20'
docker exec odoo_saas_postgres20 psql -U odoo -d postgres -Atc 'show server_version_num' | grep -Eq '^1[6-9][0-9]{4}$'
for manifest in web_studio web_enterprise account_accountant; do
    [ -f "$ENTERPRISE20_PATH/$manifest/__manifest__.py" ] || fail "Enterprise 20 module missing: $manifest"
done
if [ -d "$PLATFORM_ROOT/nginx-tenants" ]; then
    TENANT_CONFIG_CHECKSUM=$(find "$PLATFORM_ROOT/nginx-tenants" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)
fi

mkdir -p "$BACKUP_DIR"/{database,filestore,code,host} "$RELEASE_DIR"
chmod 700 "$BACKUP_DIR" "$RELEASE_DIR"

# Back up and validate every Odoo 19 database before changing host routing.
docker exec "$PG19_CONTAINER" pg_dumpall -U odoo --globals-only > "$BACKUP_DIR/database/globals.sql"
mapfile -t databases < <(docker exec "$PG19_CONTAINER" psql -U odoo -d postgres -Atc \
    "select datname from pg_database where datallowconn and not datistemplate and datname <> 'postgres' order by datname")
[ "${#databases[@]}" -gt 0 ] || fail 'no Odoo 19 databases found to back up'
for db in "${databases[@]}"; do
    [[ "$db" =~ ^[A-Za-z0-9_.-]+$ ]] || fail "unsafe database name: $db"
    docker exec "$PG19_CONTAINER" pg_dump -U odoo -Fc --no-owner --no-acl "$db" > "$BACKUP_DIR/database/$db.dump"
    docker exec -i "$PG19_CONTAINER" pg_restore --list < "$BACKUP_DIR/database/$db.dump" >/dev/null
done

# Prove that the control database dump can be restored before activation.
SOURCE_DB=odoo
printf '%s\n' "${databases[@]}" | grep -qx "$SOURCE_DB" || SOURCE_DB=${databases[0]}
docker exec "$PG19_CONTAINER" createdb -U odoo -O odoo "$SCRATCH_DB"
docker exec -i "$PG19_CONTAINER" pg_restore -U odoo -d "$SCRATCH_DB" --exit-on-error --no-owner --no-acl < "$BACKUP_DIR/database/$SOURCE_DB.dump"
source_tables=$(docker exec "$PG19_CONTAINER" psql -U odoo -d "$SOURCE_DB" -Atc "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'")
restore_tables=$(docker exec "$PG19_CONTAINER" psql -U odoo -d "$SCRATCH_DB" -Atc "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'")
[ "$source_tables" = "$restore_tables" ] || fail "restore verification table count mismatch ($source_tables != $restore_tables)"
docker exec "$PG19_CONTAINER" dropdb -U odoo --force "$SCRATCH_DB"

# Back up filestores from both Odoo 19 editions when present.
docker exec "$ODOO19_CONTAINER" tar -C /var/lib/odoo -czf - filestore > "$BACKUP_DIR/filestore/community.tar.gz"
tar -tzf "$BACKUP_DIR/filestore/community.tar.gz" >/dev/null
if docker inspect "$ODOO19_ENTERPRISE_CONTAINER" >/dev/null 2>&1; then
    docker exec "$ODOO19_ENTERPRISE_CONTAINER" tar -C /var/lib/odoo -czf - filestore > "$BACKUP_DIR/filestore/enterprise.tar.gz"
    tar -tzf "$BACKUP_DIR/filestore/enterprise.tar.gz" >/dev/null
fi

# Back up deployed code and runtime configuration checksums.
tar -C "$PLATFORM_ROOT" -czf "$BACKUP_DIR/code/deployed-addons.tar.gz" addons
tar -tzf "$BACKUP_DIR/code/deployed-addons.tar.gz" >/dev/null
for item in config docker-compose.yml nginx-tenant-template.conf provision_tenant_cert.sh; do
    [ ! -e "$PLATFORM_ROOT/$item" ] || cp -a "$PLATFORM_ROOT/$item" "$BACKUP_DIR/host/"
done
[ ! -f /usr/local/bin/saas-tenant-provisioner.sh ] || cp -a /usr/local/bin/saas-tenant-provisioner.sh "$BACKUP_DIR/host/"
[ ! -f /usr/local/bin/saas-cert-sweeper.sh ] || cp -a /usr/local/bin/saas-cert-sweeper.sh "$BACKUP_DIR/host/"
(cd "$BACKUP_DIR" && find database filestore code host -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
(cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)

tar -xzf "$RELEASE_ARCHIVE" -C "$RELEASE_DIR"
for required_file in \
    docker/odoo20/docker-compose.tenants.yml \
    scripts/install_tenant_provisioner.sh \
    scripts/saas-cert-sweeper.sh \
    scripts/saas-tenant-destroyer.sh \
    scripts/patch_nginx_odoo20_upstreams.sh \
    scripts/provision_tenant_cert.sh; do
    [ -f "$RELEASE_DIR/$required_file" ] || fail "release file missing: $required_file"
done

ENV_SOURCE=${ODOO20_ENV_SOURCE:-/opt/odoo20-staging/repo/docker/odoo20/.env}
[ -f "$ENV_SOURCE" ] || fail "Odoo 20 environment file missing: $ENV_SOURCE"
install -m 600 "$ENV_SOURCE" "$RELEASE_DIR/docker/odoo20/.env"
if [ -L "$CURRENT_LINK" ]; then
    PREVIOUS_RELEASE=$(readlink -f "$CURRENT_LINK")
elif [ -f /opt/odoo20-staging/repo/docker/odoo20/docker-compose.tenants.yml ]; then
    PREVIOUS_RELEASE=/opt/odoo20-staging/repo
fi
ACTIVATION_STARTED=1
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"

export ODOO20_ENTERPRISE_PATH="$ENTERPRISE20_PATH"
docker compose -p "$ODOO20_COMPOSE_PROJECT" -f "$RELEASE_DIR/docker/odoo20/docker-compose.tenants.yml" --env-file "$RELEASE_DIR/docker/odoo20/.env" up -d --build
wait_container_healthy odoo_saas_postgres20
wait_container_healthy odoo_saas_20_community
wait_container_healthy odoo_saas_20_enterprise

# Disposable database smoke tests both editions; cleanup failure also fails deployment.
for edition in community enterprise; do
    smoke_db="cb20${edition}${STAMP//[^0-9]/}"
    app_container="odoo_saas_20_${edition}"
    modules=base,web
    [ "$edition" != enterprise ] || modules=base,web,web_enterprise,web_studio,account_accountant
    docker exec odoo_saas_postgres20 createdb -U odoo -O odoo "$smoke_db"
    docker exec "$app_container" odoo --config=/etc/odoo/odoo.conf -d "$smoke_db" -i "$modules" --without-demo --load-language=ar_001 --no-http --stop-after-init
    docker exec odoo_saas_postgres20 psql -U odoo -d "$smoke_db" -Atc "select count(*) from ir_module_module where state='installed'" | grep -Eq '^[1-9][0-9]*$'
    docker exec "$app_container" python3 -c '
import sys, urllib.request
url, host = sys.argv[1:]
request = urllib.request.Request(url, headers={"Host": host, "Cookie": "frontend_lang=ar_001"})
with urllib.request.urlopen(request, timeout=30) as response:
    body = response.read().decode("utf-8", "replace")
    assert response.status == 200
    assert "viewport" in body.lower()
    assert "web/login" in body
' "http://127.0.0.1:8069/web/login?db=$smoke_db" "$smoke_db.odoo.clickbulid.com"
    docker exec odoo_saas_postgres20 dropdb -U odoo --force "$smoke_db"
done

install -m 755 "$RELEASE_DIR/scripts/provision_tenant_cert.sh" "$PLATFORM_ROOT/provision_tenant_cert.sh"
bash "$RELEASE_DIR/scripts/patch_nginx_odoo20_upstreams.sh"
bash "$RELEASE_DIR/scripts/install_tenant_provisioner.sh"
docker exec "$NGINX_CONTAINER" nginx -t
test "$(systemctl is-active saas-cert-sweeper.timer)" = active
test "$(docker exec "$ODOO19_CONTAINER" odoo --version)" = "$ODOO19_VERSION"
grep -q 'upstream odoo20_backend' "$PLATFORM_ROOT/config/nginx.conf"
grep -q '^ODOO_VERSION=20$' /usr/local/bin/saas-tenant-provisioner.sh
if [ -n "$TENANT_CONFIG_CHECKSUM" ]; then
    test "$(find "$PLATFORM_ROOT/nginx-tenants" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum)" = "$TENANT_CONFIG_CHECKSUM"
fi

printf 'PASS: new tenants are pinned to Odoo 20; existing Odoo 19 tenants are unchanged.\n'
printf 'Backup: %s\nRelease: %s\n' "$BACKUP_DIR" "$RELEASE_DIR"
trap - ERR
