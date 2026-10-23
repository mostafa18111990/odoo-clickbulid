#!/usr/bin/env bash
# Install licensed Odoo 20 Enterprise add-ons from a server-local archive or
# extracted directory, then verify them with an isolated disposable database.
set -Eeuo pipefail
umask 027

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_DIR="$ROOT_DIR/docker/odoo20"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.tenants.yml"
ENV_FILE="$COMPOSE_DIR/.env"
PROJECT_NAME=clickbuild-odoo20-tenants
DB_CONTAINER=odoo_saas_postgres20
ODOO_CONTAINER=odoo_saas_20_enterprise
ENTERPRISE_DEST=/opt/odoo-saas/enterprise20
SMOKE_DB="cb20entsmoke$(date +%Y%m%d%H%M%S)"
SMOKE_LOG="/tmp/${SMOKE_DB}.log"
TEMP_DIR=""
STAGED_DIR=""
SMOKE_CREATED=0

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

cleanup() {
    if [ "$SMOKE_CREATED" = "1" ]; then
        if ! docker exec "$DB_CONTAINER" dropdb -U odoo --force --if-exists "$SMOKE_DB" >/dev/null 2>&1; then
            echo "WARN: could not remove disposable Enterprise smoke database $SMOKE_DB" >&2
        fi
        if ! docker exec "$ODOO_CONTAINER" rm -rf "/var/lib/odoo/filestore/$SMOKE_DB" >/dev/null 2>&1; then
            echo "WARN: could not remove disposable Enterprise smoke filestore $SMOKE_DB" >&2
        fi
    fi
    [ -z "$TEMP_DIR" ] || rm -rf -- "$TEMP_DIR"
    [ -z "$STAGED_DIR" ] || rm -rf -- "$STAGED_DIR"
    rm -f -- "$SMOKE_LOG"
}
trap cleanup EXIT

[ "$(id -u)" -eq 0 ] || fail "run as root"
[ "$#" -eq 1 ] || fail "usage: $0 /path/to/official-odoo20-enterprise-source"
command -v docker >/dev/null || fail "Docker is not installed"
docker compose version >/dev/null || fail "Docker Compose v2 is not installed"
[ -f "$COMPOSE_FILE" ] || fail "compose file missing: $COMPOSE_FILE"
[ -f "$ENV_FILE" ] || fail "staging env file missing; run bootstrap_odoo20_tenant_staging.sh first"

SOURCE_PATH=$(readlink -f -- "$1")
[ -e "$SOURCE_PATH" ] || fail "Enterprise source does not exist: $SOURCE_PATH"
[ -r "$SOURCE_PATH" ] || fail "Enterprise source is not readable: $SOURCE_PATH"
[ ! -e "$ENTERPRISE_DEST" ] || fail "$ENTERPRISE_DEST already exists; refusing to overwrite it"

if [ -d "$SOURCE_PATH" ]; then
    SEARCH_ROOT="$SOURCE_PATH"
else
    TEMP_DIR=$(mktemp -d /tmp/odoo20-enterprise.XXXXXX)
    case "$SOURCE_PATH" in
        *.zip)
            command -v unzip >/dev/null || fail "unzip is required for a ZIP archive"
            unzip -q "$SOURCE_PATH" -d "$TEMP_DIR"
            ;;
        *.tar|*.tar.gz|*.tgz|*.tar.bz2|*.tbz2|*.tar.xz|*.txz)
            tar -xf "$SOURCE_PATH" -C "$TEMP_DIR"
            ;;
        *)
            fail "use an extracted directory, .zip, .tar.gz, .tgz, .tar.bz2, or .tar.xz archive"
            ;;
    esac
    SEARCH_ROOT="$TEMP_DIR"
fi

WEB_STUDIO_MANIFEST=$(find "$SEARCH_ROOT" -type f \
    -path '*/web_studio/__manifest__.py' -print -quit)
[ -n "$WEB_STUDIO_MANIFEST" ] || fail "official Enterprise source validation failed: web_studio is missing"
ENTERPRISE_ROOT=$(dirname "$(dirname "$WEB_STUDIO_MANIFEST")")
[ -f "$ENTERPRISE_ROOT/web_enterprise/__manifest__.py" ] \
    || fail "official Enterprise source validation failed: web_enterprise is missing"
[ -f "$ENTERPRISE_ROOT/account_accountant/__manifest__.py" ] \
    || fail "official Enterprise source validation failed: account_accountant is missing"

install -d -m 0755 /opt/odoo-saas
STAGED_DIR=$(mktemp -d /opt/odoo-saas/.enterprise20.XXXXXX)
cp -a "$ENTERPRISE_ROOT/." "$STAGED_DIR/"
chown -R root:root "$STAGED_DIR"
find "$STAGED_DIR" -type d -exec chmod 0755 {} +
find "$STAGED_DIR" -type f -exec chmod a+r {} +
mv "$STAGED_DIR" "$ENTERPRISE_DEST"
STAGED_DIR=""

cd "$COMPOSE_DIR"
docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" \
    up -d odoo20-enterprise

for _ in $(seq 1 60); do
    ODOO_HEALTH=$(docker inspect "$ODOO_CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null || true)
    [ "$ODOO_HEALTH" != unhealthy ] || {
        docker logs --tail 80 "$ODOO_CONTAINER" >&2
        fail "Odoo 20 Enterprise staging container became unhealthy"
    }
    [ "$ODOO_HEALTH" = healthy ] && break
    sleep 5
done
[ "${ODOO_HEALTH:-}" = healthy ] || fail "Odoo 20 Enterprise staging container is not healthy"
docker exec "$ODOO_CONTAINER" odoo --version | grep -q 'Odoo Server 20' \
    || fail "Enterprise staging container is not Odoo 20"

docker exec "$DB_CONTAINER" createdb -U odoo -O odoo "$SMOKE_DB"
SMOKE_CREATED=1
if ! docker exec "$ODOO_CONTAINER" odoo \
        --config=/etc/odoo/odoo.conf \
        -d "$SMOKE_DB" \
        -i base,web,web_enterprise,account_accountant,saas_tenant_login_helper \
        --without-demo \
        --load-language=ar_001 \
        --no-http --stop-after-init >"$SMOKE_LOG" 2>&1; then
    tail -80 "$SMOKE_LOG" >&2
    fail "Odoo 20 Enterprise smoke database initialization failed"
fi
if grep -E 'ERROR|CRITICAL|Traceback' "$SMOKE_LOG"; then
    fail "Odoo 20 Enterprise smoke log contains an error"
fi

for MODULE in web_enterprise account_accountant saas_tenant_login_helper; do
    MODULE_STATE=$(docker exec "$DB_CONTAINER" psql -U odoo -d "$SMOKE_DB" -Atc \
        "select state from ir_module_module where name='$MODULE'")
    [ "$MODULE_STATE" = installed ] || fail "$MODULE was not installed"
done

docker exec "$ODOO_CONTAINER" curl -fsS \
    -H "Host: ${SMOKE_DB}.odoo.clickbulid.com" \
    http://127.0.0.1:8069/web/login >/dev/null \
    || fail "Odoo 20 Enterprise login route smoke test failed"

echo "PASS: isolated Odoo 20 Enterprise staging is healthy"
echo "Odoo: $(docker exec "$ODOO_CONTAINER" odoo --version)"
