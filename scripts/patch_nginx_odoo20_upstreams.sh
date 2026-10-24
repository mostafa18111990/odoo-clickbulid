#!/bin/bash
# Add isolated Odoo 20 Community/Enterprise upstreams to the platform nginx.
set -e

CONF=${NGINX_CONF:-/opt/odoo-saas/config/nginx.conf}
MARKER='upstream odoo20_backend'

[ -f "$CONF" ] || { echo "FAIL: nginx config missing: $CONF"; exit 2; }
if grep -q "$MARKER" "$CONF"; then
    echo "[odoo20_upstreams] already present"
    exit 0
fi

cp "$CONF" "$CONF.bak.odoo20.$(date +%s)"
python3 - "$CONF" <<'PY'
import sys

path = sys.argv[1]
with open(path, encoding='utf-8') as handle:
    content = handle.read()
needle = '    upstream odoo_backend'
assert needle in content, 'existing Odoo upstream block not found'
block = '''    # Isolated Odoo 20 tenant plane.
    upstream odoo20_backend         { server odoo20_community:8069; keepalive 32; }
    upstream odoo20_longpolling     { server odoo20_community:8072; keepalive 8; }
    upstream odoo20_ent_backend     { server odoo20_enterprise:8069; keepalive 32; }
    upstream odoo20_ent_longpolling { server odoo20_enterprise:8072; keepalive 8; }

'''
content = content.replace(needle, block + needle, 1)
with open(path, 'w', encoding='utf-8') as handle:
    handle.write(content)
PY

docker exec odoo_saas_nginx nginx -t
docker exec odoo_saas_nginx nginx -s reload
echo "[odoo20_upstreams] installed"
