#!/bin/bash
# Protected production deployment for the business-sector catalog.
set -Eeuo pipefail
umask 077

RELEASE_ARCHIVE=${1:-}
RELEASE_SHA=${2:-}
PLATFORM_ROOT=${PLATFORM_ROOT:-/opt/odoo-saas}
BACKUP_ROOT=${BACKUP_ROOT:-$PLATFORM_ROOT/backups}
PG_CONTAINER=${PG_CONTAINER:-odoo_saas_postgres}
APP_CONTAINER=${APP_CONTAINER:-odoo_saas_app}
ENTERPRISE_CONTAINER=${ENTERPRISE_CONTAINER:-odoo_saas_ent}
CONTROL_DB=${CONTROL_DB:-odoo}
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$BACKUP_ROOT/pre-sector-catalog-$STAMP"
SCRATCH_DB="cbsectorpre${STAMP//[^0-9]/}"
LOCK_FILE=/run/lock/clickbuild-sector-production.lock
MODULES=(saas_tenant_manager saas_core saas_website)
DEPLOY_STARTED=0
APP_WAS_RUNNING=0
ENTERPRISE_WAS_RUNNING=0
WORK_DIR=''
APP_IMAGE=''
APP_NETWORK=''

fail() { printf 'FAIL: %s\n' "$*" >&2; return 1; }
container_state() { docker inspect --format '{{.State.Status}}' "$1"; }
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
    fail "$container did not become healthy within 180 seconds"
}
drop_scratch() {
    if docker inspect "$PG_CONTAINER" >/dev/null 2>&1; then
        docker exec "$PG_CONTAINER" dropdb -U odoo --if-exists --force "$SCRATCH_DB"
    fi
}
restore_filestore() {
    docker exec "$APP_CONTAINER" sh -c 'find /var/lib/odoo/filestore -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
    docker exec -i "$APP_CONTAINER" tar -C /var/lib/odoo -xzf - < "$BACKUP_DIR/filestore/community.tar.gz"
    if [ -f "$BACKUP_DIR/filestore/enterprise.tar.gz" ] && docker inspect "$ENTERPRISE_CONTAINER" >/dev/null 2>&1; then
        docker exec "$ENTERPRISE_CONTAINER" sh -c 'find /var/lib/odoo/filestore -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +'
        docker exec -i "$ENTERPRISE_CONTAINER" tar -C /var/lib/odoo -xzf - < "$BACKUP_DIR/filestore/enterprise.tar.gz"
    fi
}
start_apps() {
    if [ "$APP_WAS_RUNNING" -eq 1 ]; then
        docker start "$APP_CONTAINER"
        wait_container_healthy "$APP_CONTAINER"
    fi
    if [ "$ENTERPRISE_WAS_RUNNING" -eq 1 ]; then
        docker start "$ENTERPRISE_CONTAINER"
        wait_container_healthy "$ENTERPRISE_CONTAINER"
    fi
}
rollback() {
    local rc=$?
    trap - ERR
    printf 'Deployment failed; restoring verified backup %s\n' "$BACKUP_DIR" >&2
    if [ "$DEPLOY_STARTED" -eq 1 ]; then
        if [ "$(container_state "$APP_CONTAINER")" = running ]; then docker stop "$APP_CONTAINER"; fi
        if docker inspect "$ENTERPRISE_CONTAINER" >/dev/null 2>&1 && [ "$(container_state "$ENTERPRISE_CONTAINER")" = running ]; then
            docker stop "$ENTERPRISE_CONTAINER"
        fi
        for module in "${MODULES[@]}"; do
            if [ -d "$PLATFORM_ROOT/addons/$module" ]; then
                mv "$PLATFORM_ROOT/addons/$module" "$WORK_DIR/failed-$module"
            fi
            cp -a "$BACKUP_DIR/code/modules/$module" "$PLATFORM_ROOT/addons/$module"
        done
        docker exec "$PG_CONTAINER" dropdb -U odoo --if-exists --force "$CONTROL_DB"
        docker exec "$PG_CONTAINER" createdb -U odoo -O odoo "$CONTROL_DB"
        docker exec -i "$PG_CONTAINER" pg_restore -U odoo -d "$CONTROL_DB" --exit-on-error --no-owner --no-acl \
            < "$BACKUP_DIR/database/$CONTROL_DB.dump"
        start_apps
        restore_filestore
        if [ "$APP_WAS_RUNNING" -eq 1 ]; then docker restart "$APP_CONTAINER"; wait_container_healthy "$APP_CONTAINER"; fi
        if [ "$ENTERPRISE_WAS_RUNNING" -eq 1 ]; then docker restart "$ENTERPRISE_CONTAINER"; wait_container_healthy "$ENTERPRISE_CONTAINER"; fi
    fi
    drop_scratch
    exit "$rc"
}
trap rollback ERR

[ "$(id -u)" -eq 0 ] || fail 'run as root'
[ -f "$RELEASE_ARCHIVE" ] || fail 'release archive is required'
[[ "$RELEASE_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'release SHA must be a 40-character commit id'
exec 9>"$LOCK_FILE"
flock -n 9 || fail 'another sector deployment is running'

for container in "$PG_CONTAINER" "$APP_CONTAINER"; do
    docker inspect "$container" >/dev/null 2>&1 || fail "missing container: $container"
done
container_healthy "$PG_CONTAINER"
container_healthy "$APP_CONTAINER"
docker exec "$APP_CONTAINER" odoo --version | grep -q 'Odoo Server 19'
docker exec "$PG_CONTAINER" psql -U odoo -d "$CONTROL_DB" -Atc 'select 1' | grep -qx 1

APP_IMAGE=$(docker inspect --format '{{.Config.Image}}' "$APP_CONTAINER")
APP_NETWORK=$(docker inspect --format '{{range $name, $settings := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' "$APP_CONTAINER" | head -n1)
[ -n "$APP_IMAGE" ] || fail 'could not determine the Odoo 19 image'
[ -n "$APP_NETWORK" ] || fail 'could not determine the Odoo network'
WORK_DIR=$(mktemp -d /run/clickbuild-sector-production.XXXXXX)
mkdir -p "$BACKUP_DIR"/{database,filestore,code/modules,runtime} "$WORK_DIR/release"
chmod 700 "$BACKUP_DIR" "$WORK_DIR"

# Create and verify database backups before any production mutation.
docker exec "$PG_CONTAINER" pg_dumpall -U odoo --globals-only > "$BACKUP_DIR/database/globals.sql"
mapfile -t databases < <(docker exec "$PG_CONTAINER" psql -U odoo -d postgres -Atc \
    "select datname from pg_database where datallowconn and not datistemplate and datname <> 'postgres' order by datname")
[ "${#databases[@]}" -gt 0 ] || fail 'no Odoo databases found to back up'
printf '%s\n' "${databases[@]}" | grep -qx "$CONTROL_DB" || fail "control database not found: $CONTROL_DB"
for db in "${databases[@]}"; do
    [[ "$db" =~ ^[A-Za-z0-9_.-]+$ ]] || fail "unsafe database name: $db"
    docker exec "$PG_CONTAINER" pg_dump -U odoo -Fc --no-owner --no-acl "$db" > "$BACKUP_DIR/database/$db.dump"
    docker exec -i "$PG_CONTAINER" pg_restore --list < "$BACKUP_DIR/database/$db.dump" >/dev/null
done

# Verify the control dump by restoring it to an isolated database.
docker exec "$PG_CONTAINER" createdb -U odoo -O odoo "$SCRATCH_DB"
docker exec -i "$PG_CONTAINER" pg_restore -U odoo -d "$SCRATCH_DB" --exit-on-error --no-owner --no-acl \
    < "$BACKUP_DIR/database/$CONTROL_DB.dump"
source_tables=$(docker exec "$PG_CONTAINER" psql -U odoo -d "$CONTROL_DB" -Atc \
    "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'")
restore_tables=$(docker exec "$PG_CONTAINER" psql -U odoo -d "$SCRATCH_DB" -Atc \
    "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'")
[ "$source_tables" = "$restore_tables" ] || fail "restore table count mismatch ($source_tables != $restore_tables)"

# Back up filestore, deployed modules, and runtime configuration.
docker exec "$APP_CONTAINER" tar -C /var/lib/odoo -czf - filestore > "$BACKUP_DIR/filestore/community.tar.gz"
tar -tzf "$BACKUP_DIR/filestore/community.tar.gz" >/dev/null
if docker inspect "$ENTERPRISE_CONTAINER" >/dev/null 2>&1; then
    docker exec "$ENTERPRISE_CONTAINER" tar -C /var/lib/odoo -czf - filestore > "$BACKUP_DIR/filestore/enterprise.tar.gz"
    tar -tzf "$BACKUP_DIR/filestore/enterprise.tar.gz" >/dev/null
fi
tar -C "$PLATFORM_ROOT" -czf "$BACKUP_DIR/code/deployed-addons.tar.gz" addons
tar -tzf "$BACKUP_DIR/code/deployed-addons.tar.gz" >/dev/null
for module in "${MODULES[@]}"; do
    [ -f "$PLATFORM_ROOT/addons/$module/__manifest__.py" ] || fail "deployed module missing: $module"
    cp -a "$PLATFORM_ROOT/addons/$module" "$BACKUP_DIR/code/modules/$module"
done
for item in config docker-compose.yml nginx-tenant-template.conf; do
    if [ -e "$PLATFORM_ROOT/$item" ]; then cp -a "$PLATFORM_ROOT/$item" "$BACKUP_DIR/runtime/"; fi
done
(cd "$BACKUP_DIR" && find database filestore code runtime -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
(cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)

tar -xzf "$RELEASE_ARCHIVE" -C "$WORK_DIR/release"
for module in "${MODULES[@]}"; do
    [ -f "$WORK_DIR/release/addons/$module/__manifest__.py" ] || fail "release module missing: $module"
done

# Rehearse the exact module upgrade on the restored control database first.
docker run --rm --network "$APP_NETWORK" --volumes-from "$APP_CONTAINER" \
    -v "$WORK_DIR/release/addons:/mnt/candidate:ro" "$APP_IMAGE" odoo \
    --config=/etc/odoo/odoo.conf \
    --addons-path=/mnt/candidate,/mnt/extra-addons,/mnt/oca,/usr/lib/python3/dist-packages/odoo/addons \
    -d "$SCRATCH_DB" -u saas_tenant_manager,saas_core,saas_website \
    --without-demo --no-http --stop-after-init
docker exec "$PG_CONTAINER" psql -U odoo -d "$SCRATCH_DB" -Atc \
    "select count(*) from ir_model_fields where model='saas.tenant' and name='business_sector'" | grep -qx 1
docker exec "$PG_CONTAINER" psql -U odoo -d "$SCRATCH_DB" -Atc \
    "select count(*) from ir_module_module where name in ('saas_tenant_manager','saas_core','saas_website') and state='installed'" | grep -qx 3

# Deploy only the three reviewed modules, with a short controlled outage.
APP_WAS_RUNNING=1
if docker inspect "$ENTERPRISE_CONTAINER" >/dev/null 2>&1 && [ "$(container_state "$ENTERPRISE_CONTAINER")" = running ]; then
    ENTERPRISE_WAS_RUNNING=1
fi
docker stop "$APP_CONTAINER"
if [ "$ENTERPRISE_WAS_RUNNING" -eq 1 ]; then docker stop "$ENTERPRISE_CONTAINER"; fi
DEPLOY_STARTED=1
for module in "${MODULES[@]}"; do
    cp -a "$WORK_DIR/release/addons/$module" "$WORK_DIR/new-$module"
    mv "$PLATFORM_ROOT/addons/$module" "$WORK_DIR/old-$module"
    mv "$WORK_DIR/new-$module" "$PLATFORM_ROOT/addons/$module"
    chown -R --reference="$WORK_DIR/old-$module" "$PLATFORM_ROOT/addons/$module"
done

docker run --rm --network "$APP_NETWORK" --volumes-from "$APP_CONTAINER" "$APP_IMAGE" odoo \
    --config=/etc/odoo/odoo.conf \
    -d "$CONTROL_DB" -u saas_tenant_manager,saas_core,saas_website \
    --without-demo --no-http --stop-after-init
start_apps

# Production smoke tests. Any failure invokes the rollback above.
docker exec "$PG_CONTAINER" psql -U odoo -d "$CONTROL_DB" -Atc \
    "select count(*) from ir_model_fields where model='saas.tenant' and name='business_sector'" | grep -qx 1
docker exec "$PG_CONTAINER" psql -U odoo -d "$CONTROL_DB" -Atc \
    "select count(*) from ir_module_module where name in ('saas_tenant_manager','saas_core','saas_website') and state='installed'" | grep -qx 3
docker exec "$APP_CONTAINER" python3 -c '
import urllib.request
for path, required in (("/web/login?db=odoo", "web/login"), ("/get-started?db=odoo", "business_sector")):
    request = urllib.request.Request("http://127.0.0.1:8069" + path, headers={"Host": "odoo.clickbulid.com", "Cookie": "frontend_lang=ar_001"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", "replace")
        assert response.status == 200
        assert required in body
'

drop_scratch
printf 'PASS: sector catalog deployed to the Odoo 19 control plane.\n'
printf 'Backup: %s\nRelease SHA: %s\n' "$BACKUP_DIR" "$RELEASE_SHA"
trap - ERR

