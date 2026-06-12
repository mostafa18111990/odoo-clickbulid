#!/bin/bash
# Provision a Let's Encrypt cert for a new tenant subdomain.
# Usage: ./provision_tenant_cert.sh <tenant_subdomain>
#   e.g. ./provision_tenant_cert.sh acme  -> acme.odoo.clickbulid.com
#
# Architecture:
#   clickbulid.com           -> marketing site (not handled here)
#   odoo.clickbulid.com      -> SaaS master/admin (DB: odoo)
#   <sub>.odoo.clickbulid.com -> tenant (DB: <sub>)
#
# Each tenant gets a dedicated nginx server block (so SNI delivers the
# right cert per tenant) auto-written from the shared template.
set -e
SUB="$1"
PARENT="odoo.clickbulid.com"
EMAIL="admin@clickbulid.com"
TEMPLATE=/opt/odoo-saas/nginx-tenant-template.conf
TENANTS_DIR=/opt/odoo-saas/nginx-tenants
REQ_DIR=/opt/odoo-saas/cert-requests

if [ -z "$SUB" ]; then
    echo "Usage: $0 <tenant_subdomain>"
    exit 1
fi

FQDN="${SUB}.${PARENT}"

# Determine the tenant's Odoo edition.
# Source of truth: the .req file the sweeper left for us (key edition=...).
# Fall back to `community` if not set (legacy tenants pre-Phase-D).
EDITION=community
if [ -f "$REQ_DIR/$SUB.req" ]; then
    val=$(grep -E '^edition=' "$REQ_DIR/$SUB.req" | head -1 | cut -d'=' -f2-)
    [ -n "$val" ] && EDITION="$val"
fi
case "$EDITION" in
    enterprise)
        NGINX_BACKEND=odoo_ent_backend
        NGINX_WEBSOCKET=odoo_ent_longpolling
        ;;
    *)
        NGINX_BACKEND=odoo_backend
        NGINX_WEBSOCKET=odoo_longpolling
        ;;
esac
echo "[provision] edition=$EDITION → backend=$NGINX_BACKEND, ws=$NGINX_WEBSOCKET"

echo "[provision] checking DNS for $FQDN..."
if command -v dig >/dev/null 2>&1; then
    RESOLVED=$(dig +short A "$FQDN" | head -1)
elif command -v host >/dev/null 2>&1; then
    RESOLVED=$(host -t A "$FQDN" 2>/dev/null | awk '/has address/ {print $4; exit}')
else
    RESOLVED=$(getent hosts "$FQDN" | awk '{print $1; exit}')
fi
EXPECTED=$(curl -sS https://ifconfig.me)
if [ -z "$RESOLVED" ]; then
    echo "FAIL: $FQDN does not resolve. Add A-record first."
    exit 2
fi
if [ "$RESOLVED" != "$EXPECTED" ]; then
    echo "WARN: $FQDN resolves to $RESOLVED but server IP is $EXPECTED"
fi

# Skip certbot if a valid cert already exists
if [ -f "/etc/letsencrypt/live/$FQDN/fullchain.pem" ]; then
    echo "[provision] cert already exists for $FQDN, reusing"
else
    echo "[provision] requesting cert for $FQDN..."
    certbot certonly \
        --webroot -w /opt/odoo-saas/certbot/www \
        -d "$FQDN" \
        --non-interactive --agree-tos \
        --email "$EMAIL" \
        --rsa-key-size 4096
fi

# Render tenant server block from template (substitute __FQDN__)
if [ ! -f "$TEMPLATE" ]; then
    echo "FAIL: template missing at $TEMPLATE"
    exit 3
fi
mkdir -p "$TENANTS_DIR"
sed \
    -e "s|__FQDN__|$FQDN|g" \
    -e "s|__BACKEND__|$NGINX_BACKEND|g" \
    -e "s|__WEBSOCKET__|$NGINX_WEBSOCKET|g" \
    "$TEMPLATE" > "$TENANTS_DIR/$SUB.conf"
echo "[provision] wrote $TENANTS_DIR/$SUB.conf"

echo "[provision] reloading nginx..."
docker exec odoo_saas_nginx nginx -t
docker exec odoo_saas_nginx nginx -s reload

echo "[provision] done. Cert at /etc/letsencrypt/live/$FQDN/"
echo "[provision] verifying SNI cert delivery:"
echo | openssl s_client -connect 127.0.0.1:443 -servername "$FQDN" 2>/dev/null \
    | openssl x509 -noout -subject -dates
