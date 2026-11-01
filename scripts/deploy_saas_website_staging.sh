#!/bin/bash
# Deploy saas_website to the isolated Odoo 20 staging plane, then verify it
# against a disposable database. Any failure restores the previous module.
set -Eeuo pipefail
umask 077

ARCHIVE=${1:-}
EXPECTED_SHA=${2:-}
RUN_ID=${3:-}
STAGING_ROOT=${STAGING_ROOT:-/opt/odoo20-staging/repo}
BACKUP_ROOT=${BACKUP_ROOT:-/opt/odoo20-staging/backups}
DB_CONTAINER=${DB_CONTAINER:-odoo_saas_postgres20}
ODOO_CONTAINER=${ODOO_CONTAINER:-odoo_saas_20_community}
MODULE_DIR="$STAGING_ROOT/addons/saas_website"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="$BACKUP_ROOT/saas-website-$STAMP-$RUN_ID"
SMOKE_DB="cbwebsite${RUN_ID}"
TMP_DIR=
DEPLOY_STARTED=0
SMOKE_CREATED=0

fail() {
    echo "FAIL: $*" >&2
    return 1
}

container_healthy() {
    local container=$1 state
    state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
    [ "$state" = healthy ] || [ "$state" = running ] || fail "$container is not healthy (state=$state)"
}

wait_for_odoo() {
    local state
    for _ in $(seq 1 60); do
        state=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$ODOO_CONTAINER" 2>/dev/null || true)
        if [ "$state" = healthy ] || [ "$state" = running ]; then
            return 0
        fi
        sleep 2
    done
    fail "$ODOO_CONTAINER did not become healthy"
}

cleanup() {
    local exit_code=$?
    set +e
    if [ "$SMOKE_CREATED" = 1 ]; then
        docker exec "$DB_CONTAINER" dropdb -U odoo --if-exists --force "$SMOKE_DB" >/dev/null 2>&1
        docker exec "$ODOO_CONTAINER" rm -rf "/var/lib/odoo/filestore/$SMOKE_DB" >/dev/null 2>&1
    fi
    [ -z "$TMP_DIR" ] || rm -rf "$TMP_DIR"
    return "$exit_code"
}

rollback() {
    local exit_code=$?
    trap - ERR
    set +e
    if [ "$DEPLOY_STARTED" = 1 ] && [ -d "$BACKUP_DIR/module" ]; then
        echo "ROLLBACK: restoring saas_website from $BACKUP_DIR" >&2
        rm -rf "$MODULE_DIR"
        cp -a "$BACKUP_DIR/module" "$MODULE_DIR"
        docker restart "$ODOO_CONTAINER" >/dev/null
        wait_for_odoo
        echo 'ROLLBACK_COMPLETE' >&2
    fi
    exit "$exit_code"
}

trap cleanup EXIT
trap rollback ERR

[ "$(id -u)" -eq 0 ] || fail 'run as root'
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || fail 'invalid release SHA'
[[ "$RUN_ID" =~ ^[0-9]{1,20}$ ]] || fail 'numeric GitHub run id required'
[ -f "$ARCHIVE" ] || fail "release archive not found: $ARCHIVE"
[[ "$STAGING_ROOT" == /opt/odoo20-staging/* ]] || fail 'STAGING_ROOT must remain under /opt/odoo20-staging'
[ -d "$MODULE_DIR" ] || fail "deployed module missing: $MODULE_DIR"

command -v docker >/dev/null || fail 'Docker is not installed'
command -v tar >/dev/null || fail 'tar is not installed'
container_healthy "$DB_CONTAINER"
container_healthy "$ODOO_CONTAINER"
docker exec "$ODOO_CONTAINER" odoo --version | grep -q 'Odoo Server 20' || fail 'staging container is not Odoo 20'

TMP_DIR=$(mktemp -d /tmp/clickbuild-website-staging.XXXXXX)
tar -tzf "$ARCHIVE" > "$TMP_DIR/archive-files.txt"
if grep -Eq '(^/|(^|/)\.\.(/|$))' "$TMP_DIR/archive-files.txt"; then
    fail 'release archive contains an unsafe path'
fi
tar -xzf "$ARCHIVE" -C "$TMP_DIR"
RELEASE_MODULE="$TMP_DIR/addons/saas_website"
[ -f "$RELEASE_MODULE/__manifest__.py" ] || fail 'release does not contain addons/saas_website'

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
cp -a "$MODULE_DIR" "$BACKUP_DIR/module"
tar -C "$BACKUP_DIR" -czf "$BACKUP_DIR/deployed-module.tar.gz" module
tar -tzf "$BACKUP_DIR/deployed-module.tar.gz" >/dev/null
sha256sum "$BACKUP_DIR/deployed-module.tar.gz" > "$BACKUP_DIR/SHA256SUMS"
(cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)
printf '%s\n' "$EXPECTED_SHA" > "$BACKUP_DIR/release-sha"

DEPLOY_STARTED=1
rm -rf "$MODULE_DIR"
cp -a "$RELEASE_MODULE" "$MODULE_DIR"
chown -R root:root "$MODULE_DIR"
docker restart "$ODOO_CONTAINER" >/dev/null
wait_for_odoo

docker exec "$DB_CONTAINER" createdb -U odoo -O odoo "$SMOKE_DB"
SMOKE_CREATED=1
SMOKE_LOG="$TMP_DIR/odoo-install.log"
if ! docker exec "$ODOO_CONTAINER" odoo \
        --config=/etc/odoo/odoo.conf \
        -d "$SMOKE_DB" -i saas_website \
        --without-demo --load-language=ar_001 \
        --no-http --stop-after-init >"$SMOKE_LOG" 2>&1; then
    tail -100 "$SMOKE_LOG" >&2
    fail 'saas_website installation failed'
fi
if grep -E 'ERROR|CRITICAL|Traceback' "$SMOKE_LOG"; then
    fail 'Odoo installation log contains an error'
fi

MODULE_STATE=$(docker exec "$DB_CONTAINER" psql -U odoo -d "$SMOKE_DB" -Atc \
    "select state from ir_module_module where name='saas_website'")
[ "$MODULE_STATE" = installed ] || fail "saas_website state is ${MODULE_STATE:-missing}"

SIGNUP_HTML="$TMP_DIR/get-started.html"
docker exec "$ODOO_CONTAINER" curl -fsS \
    -H "Host: ${SMOKE_DB}.odoo.clickbulid.com" \
    http://127.0.0.1:8069/get-started > "$SIGNUP_HTML"
grep -q '299' "$SIGNUP_HTML" || fail 'Community starting price 299 is missing'
grep -q '399' "$SIGNUP_HTML" || fail 'Enterprise starting price 399 is missing'
if grep -Eq '(من 99 ريال|from 99 SAR|من 599 ريال|from 599 SAR)' "$SIGNUP_HTML"; then
    fail 'legacy signup prices are still rendered'
fi

DEPLOY_STARTED=0
echo 'PASS: saas_website deployed and verified on isolated staging.'
echo "Release SHA: $EXPECTED_SHA"
echo "Backup: $BACKUP_DIR"
