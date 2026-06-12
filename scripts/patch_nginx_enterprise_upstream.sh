#!/bin/bash
# Add an `odoo_ent_backend` + `odoo_ent_longpolling` upstream to nginx.conf
# so per-tenant server blocks can route Enterprise tenants to odoo_saas_ent.
# Idempotent.
set -e
CONF=/opt/odoo-saas/config/nginx.conf
MARKER='upstream odoo_ent_backend'
if grep -q "$MARKER" "$CONF"; then
    echo "[ent_upstream] already present, skipping"
    exit 0
fi
cp "$CONF" "$CONF.bak.entupstream.$(date +%s)"

python3 - "$CONF" << 'PY'
import sys
p = sys.argv[1]
with open(p) as f: c = f.read()
# Insert next to the existing community upstreams.
old = '''    upstream odoo_backend    { server odoo:8069; keepalive 32; }
    upstream odoo_longpolling { server odoo:8072; keepalive 8; }'''
assert old in c, 'expected community upstream block not found'
new = old + '''
    # Enterprise tenants (odoo_saas_ent container — same Postgres, separate binary).
    upstream odoo_ent_backend     { server odoo_ent:8069; keepalive 32; }
    upstream odoo_ent_longpolling { server odoo_ent:8072; keepalive 8; }'''
c = c.replace(old, new, 1)
with open(p, 'w') as f: f.write(c)
print('[ent_upstream] inserted enterprise upstream block')
PY

echo "[ent_upstream] testing nginx config..."
docker exec odoo_saas_nginx nginx -t 2>&1 | grep -vE 'deprecated' | tail -3
echo "[ent_upstream] reloading..."
docker exec odoo_saas_nginx nginx -s reload
echo "[ent_upstream] done"
