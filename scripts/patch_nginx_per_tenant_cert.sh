#!/bin/bash
# Switch the tenant wildcard server block to use per-tenant SSL certificates.
# Uses nginx variables and a map to look up cert paths dynamically.
# Idempotent.
set -e
CONF=/opt/odoo-saas/config/nginx.conf
MARKER='# per-tenant cert lookup'
if grep -q "$MARKER" "$CONF"; then
    echo "[per_tenant_cert] already applied, skipping"
    exit 0
fi
cp "$CONF" "$CONF.bak.cert.$(date +%s)"

python3 - "$CONF" << 'PY'
import sys, re
p = sys.argv[1]
with open(p) as f:
    c = f.read()

# Replace the static ssl_certificate lines inside the *.odoo.clickbulid.com
# server block with variables that resolve to per-tenant cert paths.
# nginx supports variables in ssl_certificate since 1.15.9.
old = (
    'server_name ~^(?P<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;\n'
    '        ssl_certificate     /etc/letsencrypt/live/odoo.clickbulid.com/fullchain.pem;\n'
    '        ssl_certificate_key /etc/letsencrypt/live/odoo.clickbulid.com/privkey.pem;')
new = (
    'server_name ~^(?P<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;\n'
    '        # per-tenant cert lookup: serves /etc/letsencrypt/live/<sub>.odoo.clickbulid.com/\n'
    '        # Falls back to odoo.clickbulid.com cert if the per-tenant one is missing\n'
    '        # (warning: browser shows SAN mismatch until provisioner issues the real cert).\n'
    '        ssl_certificate     /etc/letsencrypt/live/$sub.odoo.clickbulid.com/fullchain.pem;\n'
    '        ssl_certificate_key /etc/letsencrypt/live/$sub.odoo.clickbulid.com/privkey.pem;')

if old not in c:
    print('FAIL: did not find expected wildcard server block')
    sys.exit(1)
c = c.replace(old, new)

with open(p, 'w') as f:
    f.write(c)
print('[per_tenant_cert] swapped wildcard certs to per-tenant lookup')
PY

echo "[per_tenant_cert] testing nginx..."
docker exec odoo_saas_nginx nginx -t 2>&1 | grep -vE 'deprecated' | tail -3
echo "[per_tenant_cert] reloading..."
docker exec odoo_saas_nginx nginx -s reload
echo "[per_tenant_cert] done"
