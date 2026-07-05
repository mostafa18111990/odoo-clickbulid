#!/bin/bash
# Prepare a customer's fresh VPS to host ClickBuild tenants remotely, OR
# verify an existing server meets the requirements the SaaS expects.
#
# Usage:
#   bootstrap_external_server.sh --check      # validate a server (non-destructive)
#   bootstrap_external_server.sh --install    # install the full stack (Ubuntu 22/24)
#
# After --install (or a passing --check), register the server in the SaaS:
#   ClickBuild SaaS -> Operations -> External Servers -> New
# with this box's SSH details. The container/role names below are the
# defaults the SaaS form ships with.
set -uo pipefail

ROOT=/opt/odoo-saas
ODOO_CONTAINER=odoo_saas_app
PG_CONTAINER=odoo_saas_postgres
NGINX_CONTAINER=odoo_saas_nginx
PG_USER=odoo
DB_OWNER=odoo_community
ODOO_IMAGE="${ODOO_IMAGE:-clickbuild/odoo-community:19}"

green() { printf '\033[0;32m%s\033[0m\n' "$1"; }
red()   { printf '\033[0;31m%s\033[0m\n' "$1"; }
yellow(){ printf '\033[1;33m%s\033[0m\n' "$1"; }

# ── CHECK MODE ────────────────────────────────────────────────────────────────
do_check() {
    local ok=1
    echo "── Checking external-server readiness ──"

    if command -v docker >/dev/null 2>&1; then green "✔ docker present ($(docker --version | cut -d, -f1))"; else red "✗ docker missing"; ok=0; fi

    for c in "$PG_CONTAINER" "$ODOO_CONTAINER" "$NGINX_CONTAINER"; do
        if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$c"; then
            green "✔ container running: $c"
        else
            red "✗ container NOT running: $c"; ok=0
        fi
    done

    if docker exec "$PG_CONTAINER" psql -U "$PG_USER" -tAc \
            "select 1 from pg_roles where rolname='$DB_OWNER'" 2>/dev/null | grep -qx 1; then
        green "✔ postgres role '$DB_OWNER' exists"
    else
        red "✗ postgres role '$DB_OWNER' missing"; ok=0
    fi

    for d in "$ROOT/nginx-tenants" "$ROOT/addons" /opt/backups/deleted; do
        if [ -d "$d" ]; then green "✔ dir: $d"; else red "✗ dir missing: $d"; ok=0; fi
    done

    if docker exec "$ODOO_CONTAINER" python3 -c "import barcode" 2>/dev/null; then
        green "✔ python-barcode in odoo image"
    else
        yellow "! python-barcode missing (healthcare module will fail to install)"
    fi

    echo "────────────────────────────────────────"
    if [ "$ok" = "1" ]; then
        green "READY ✅ — register this server in the SaaS."
        return 0
    else
        red "NOT READY ❌ — run with --install or fix the items above."
        return 1
    fi
}

# ── INSTALL MODE ──────────────────────────────────────────────────────────────
do_install() {
    echo "── Installing ClickBuild remote host stack ──"

    # 1. Docker
    if ! command -v docker >/dev/null 2>&1; then
        yellow "Installing docker…"
        curl -fsSL https://get.docker.com | sh
    fi
    systemctl enable --now docker

    # 2. Directory layout
    mkdir -p "$ROOT"/{config,addons,nginx-tenants,cert-requests,certbot/www} /opt/backups/deleted
    green "✔ directories created under $ROOT"

    # 3. Postgres password + odoo.conf
    if [ ! -f "$ROOT/.pg_password" ]; then
        openssl rand -hex 24 > "$ROOT/.pg_password"; chmod 600 "$ROOT/.pg_password"
    fi
    PGPASS=$(cat "$ROOT/.pg_password")
    if [ ! -f "$ROOT/config/odoo.conf" ]; then
        cat > "$ROOT/config/odoo.conf" <<CONF
[options]
addons_path = /mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons
data_dir = /var/lib/odoo
db_host = $PG_CONTAINER
db_port = 5432
db_user = $DB_OWNER
db_password = $PGPASS
dbfilter = ^%d\$
list_db = False
proxy_mode = True
workers = 2
CONF
        green "✔ odoo.conf written"
    fi

    # 4. docker-compose.yml
    if [ ! -f "$ROOT/docker-compose.yml" ]; then
        cat > "$ROOT/docker-compose.yml" <<COMPOSE
services:
  $PG_CONTAINER:
    image: postgres:15-alpine
    container_name: $PG_CONTAINER
    environment:
      POSTGRES_USER: $PG_USER
      POSTGRES_PASSWORD: $PGPASS
      POSTGRES_DB: postgres
    volumes:
      - ./pgdata:/var/lib/postgresql/data
    restart: unless-stopped
  $ODOO_CONTAINER:
    image: $ODOO_IMAGE
    container_name: $ODOO_CONTAINER
    depends_on: [$PG_CONTAINER]
    volumes:
      - ./config:/etc/odoo
      - ./addons:/mnt/extra-addons
      - odoo-data:/var/lib/odoo
    restart: unless-stopped
  $NGINX_CONTAINER:
    image: nginx:alpine
    container_name: $NGINX_CONTAINER
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx-tenants:/etc/nginx/conf.d:ro
      - ./certbot/www:/var/www/certbot:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
    restart: unless-stopped
volumes:
  odoo-data:
COMPOSE
        green "✔ docker-compose.yml written"
    fi

    # 5. Bring the stack up
    ( cd "$ROOT" && docker compose up -d )
    sleep 8

    # 6. Create the community DB role
    docker exec "$PG_CONTAINER" psql -U "$PG_USER" -tAc \
        "select 1 from pg_roles where rolname='$DB_OWNER'" | grep -qx 1 || \
        docker exec "$PG_CONTAINER" psql -U "$PG_USER" -c \
        "CREATE ROLE $DB_OWNER LOGIN PASSWORD '$PGPASS' CREATEDB;"
    green "✔ postgres role '$DB_OWNER' ready"

    # 7. Odoo image deps (hospital module needs python-barcode)
    docker exec -u root "$ODOO_CONTAINER" pip3 install --break-system-packages -q python-barcode 2>/dev/null || \
        yellow "! could not install python-barcode (install manually if using healthcare)"

    echo "────────────────────────────────────────"
    green "Install done. Now copy the platform addons + Cybrosys/OCA bundles into"
    echo "  $ROOT/addons  (rsync from the main server), then run: $0 --check"
}

case "${1:-}" in
    --check)   do_check ;;
    --install) do_install ;;
    *) echo "Usage: $0 --check | --install"; exit 1 ;;
esac
