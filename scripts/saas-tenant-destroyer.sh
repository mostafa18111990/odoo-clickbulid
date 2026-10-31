#!/bin/bash
set -euo pipefail

REQ="${1:-}"
REQ_DIR="/opt/odoo-saas/cert-requests"
FINAL_DIR="/opt/backups/deleted"
NGINX_DIR="/opt/odoo-saas/nginx-tenants"

if [[ -z "$REQ" || ! -f "$REQ" ]]; then
    echo "ERROR: delete request not found: $REQ" >&2
    exit 1
fi

read_json() {
    python3 - "$REQ" "$1" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as request_file:
    print(json.load(request_file).get(sys.argv[2], ""))
PY
}

SUB="$(read_json subdomain)"
TENANT_ID="$(read_json tenant_id)"
EDITION="$(read_json edition)"

if [[ ! "$SUB" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]]; then
    echo "ERROR: invalid subdomain: $SUB" >&2
    exit 1
fi
if [[ -n "$TENANT_ID" && ! "$TENANT_ID" =~ ^[0-9]+$ ]]; then
    echo "ERROR: invalid tenant id: $TENANT_ID" >&2
    exit 1
fi

DB="$SUB"
TS="$(date -u +%Y%m%d_%H%M%S)"
mkdir -p "$FINAL_DIR"

echo "=== DESTROYING tenant: $SUB (edition: ${EDITION:-unknown}) ==="

if docker exec odoo_saas_postgres psql -U odoo -d postgres -Atqc \
        "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -qx 1; then
    tmp_backup="$FINAL_DIR/.${DB}_DELETED_${TS}.sql.gz.tmp"
    final_backup="$FINAL_DIR/${DB}_DELETED_${TS}.sql.gz"
    docker exec odoo_saas_postgres pg_dump -U odoo "$DB" | gzip -1 > "$tmp_backup"
    gzip -t "$tmp_backup"
    test -s "$tmp_backup"
    mv "$tmp_backup" "$final_backup"
    echo "Backup verified: $final_backup"
    docker exec odoo_saas_postgres dropdb -U odoo --force "$DB"
    echo "Database dropped: $DB"
else
    echo "Database already absent: $DB"
fi

# Historical routing issues may have placed a tenant in either data volume.
for container in odoo_saas_app odoo_saas_ent; do
    if docker inspect "$container" >/dev/null 2>&1; then
        docker exec "$container" rm -rf -- "/var/lib/odoo/filestore/$DB"
    fi
done
echo "Filestore removed from both Odoo data volumes"

nginx_conf="$NGINX_DIR/$SUB.conf"
nginx_pending="$NGINX_DIR/$SUB.conf.pending-delete"
if [[ -f "$nginx_conf" ]]; then
    mv "$nginx_conf" "$nginx_pending"
    if docker exec odoo_saas_nginx nginx -t >/dev/null 2>&1; then
        docker exec odoo_saas_nginx nginx -s reload >/dev/null 2>&1
        rm -f "$nginx_pending"
        echo "Nginx configuration removed"
    else
        mv "$nginx_pending" "$nginx_conf"
        echo "ERROR: Nginx validation failed; configuration restored" >&2
        exit 1
    fi
fi

certbot delete --cert-name "$SUB.odoo.clickbulid.com" --non-interactive >/dev/null 2>&1 || true

find "$REQ_DIR" -maxdepth 1 -type f -name "$SUB.*" ! -name "$(basename "$REQ")" -delete

if [[ -n "$TENANT_ID" ]]; then
    docker exec odoo_saas_postgres psql -v ON_ERROR_STOP=1 -U odoo -d odoo -c \
        "UPDATE saas_tenant SET state='deleted', active=false WHERE id=$TENANT_ID AND subdomain='$SUB';"
else
    docker exec odoo_saas_postgres psql -v ON_ERROR_STOP=1 -U odoo -d odoo -c \
        "UPDATE saas_tenant SET state='deleted', active=false WHERE subdomain='$SUB';"
fi

echo "=== DONE destroying $SUB ==="
