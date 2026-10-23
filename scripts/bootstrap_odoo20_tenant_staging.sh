#!/bin/bash
# Build and smoke-test the isolated Odoo 20 tenant plane on the server.
# This script does not change the Odoo 19 stack, Nginx, or provisioning.
set -Eeuo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_DIR="$ROOT_DIR/docker/odoo20"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.tenants.yml"
ENV_FILE="$COMPOSE_DIR/.env"
PROJECT_NAME=clickbuild-odoo20-tenants
DB_CONTAINER=odoo_saas_postgres20
ODOO_CONTAINER=odoo_saas_20_community
SMOKE_DB="cb20smoke$(date +%Y%m%d%H%M%S)"
SMOKE_LOG="/tmp/${SMOKE_DB}.log"
SMOKE_CREATED=0

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

cleanup_smoke() {
    if [ "$SMOKE_CREATED" = "1" ]; then
        if ! docker exec "$DB_CONTAINER" dropdb -U odoo --if-exists "$SMOKE_DB" >/dev/null 2>&1; then
            echo "WARN: could not remove disposable smoke database $SMOKE_DB" >&2
        fi
        if ! docker exec "$ODOO_CONTAINER" rm -rf "/var/lib/odoo/filestore/$SMOKE_DB" >/dev/null 2>&1; then
            echo "WARN: could not remove disposable smoke filestore $SMOKE_DB" >&2
        fi
    fi
    rm -f "$SMOKE_LOG"
}
trap cleanup_smoke EXIT

[ "$(id -u)" -eq 0 ] || fail "run as root"
command -v docker >/dev/null || fail "Docker is not installed"
docker compose version >/dev/null || fail "Docker Compose v2 is not installed"
[ -f "$COMPOSE_FILE" ] || fail "compose file missing: $COMPOSE_FILE"

ODOO_NETWORK=${ODOO_NETWORK:-$(
    docker inspect odoo_saas_nginx \
        --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' 2>/dev/null \
        | head -n 1
)}
[ -n "$ODOO_NETWORK" ] || fail "could not detect the existing Odoo Docker network"
docker network inspect "$ODOO_NETWORK" >/dev/null || fail "Docker network not found: $ODOO_NETWORK"

if [ ! -f "$ENV_FILE" ]; then
    umask 077
    DB_PASSWORD=$(openssl rand -hex 32)
    MASTER_PASSWORD=$(openssl rand -hex 32)
    cat > "$ENV_FILE" <<EOF
ODOO20_DB_PASSWORD=$DB_PASSWORD
ODOO20_MASTER_PASSWORD=$MASTER_PASSWORD
ODOO20_ENTERPRISE_PATH=/opt/odoo-saas/enterprise20
ODOO_NETWORK=$ODOO_NETWORK
SMTP_HOST=localhost
SMTP_PORT=25
SMTP_SSL=False
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=noreply@clickbulid.com
EOF
    chmod 600 "$ENV_FILE"
fi

cd "$COMPOSE_DIR"
docker compose --env-file "$ENV_FILE" -p "$PROJECT_NAME" -f "$COMPOSE_FILE" \
    up -d --build postgres20 odoo20-community

for _ in $(seq 1 60); do
    PG_HEALTH=$(docker inspect "$DB_CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null || true)
    ODOO_HEALTH=$(docker inspect "$ODOO_CONTAINER" --format '{{.State.Health.Status}}' 2>/dev/null || true)
    if [ "$PG_HEALTH" = healthy ] && [ "$ODOO_HEALTH" = healthy ]; then
        break
    fi
    sleep 5
done
[ "${PG_HEALTH:-}" = healthy ] || fail "PostgreSQL 16 staging container is not healthy"
[ "${ODOO_HEALTH:-}" = healthy ] || fail "Odoo 20 staging container is not healthy"

docker exec "$ODOO_CONTAINER" odoo --version | grep -q 'Odoo Server 20' \
    || fail "staging container is not Odoo 20"
PG_VERSION_NUM=$(docker exec "$DB_CONTAINER" psql -U odoo -d postgres -Atc 'show server_version_num')
[ "$PG_VERSION_NUM" -ge 160000 ] || fail "staging PostgreSQL is below version 16"

docker exec "$DB_CONTAINER" createdb -U odoo -O odoo "$SMOKE_DB"
SMOKE_CREATED=1
if ! docker exec "$ODOO_CONTAINER" odoo \
        --config=/etc/odoo/odoo.conf \
        -d "$SMOKE_DB" \
        -i base,web,saas_tenant_login_helper \
        --without-demo \
        --load-language=ar_001 \
        --no-http --stop-after-init >"$SMOKE_LOG" 2>&1; then
    tail -80 "$SMOKE_LOG" >&2
    fail "Odoo 20 smoke database initialization failed"
fi
if grep -E 'ERROR|CRITICAL|Traceback' "$SMOKE_LOG"; then
    fail "Odoo 20 smoke log contains an error"
fi

MODULE_STATE=$(docker exec "$DB_CONTAINER" psql -U odoo -d "$SMOKE_DB" -Atc \
    "select state from ir_module_module where name='saas_tenant_login_helper'")
[ "$MODULE_STATE" = installed ] || fail "tenant login helper was not installed"

docker exec "$ODOO_CONTAINER" curl -fsS \
    -H "Host: ${SMOKE_DB}.odoo.clickbulid.com" \
    http://127.0.0.1:8069/web/login >/dev/null \
    || fail "Odoo 20 login route smoke test failed"

echo "PASS: isolated Odoo 20 tenant staging is healthy"
echo "Odoo: $(docker exec "$ODOO_CONTAINER" odoo --version)"
echo "PostgreSQL server_version_num: $PG_VERSION_NUM"
