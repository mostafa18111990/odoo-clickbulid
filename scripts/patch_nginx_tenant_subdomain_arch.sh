#!/bin/bash
# Switch tenant subdomain pattern from <sub>.clickbulid.com
# to the correct <sub>.odoo.clickbulid.com architecture.
# Idempotent — safe to re-run.
set -e
CONF=/opt/odoo-saas/config/nginx.conf
MARKER='# patched: tenant subdomain arch'
if grep -q "$MARKER" "$CONF"; then
    echo "[patch_arch] already applied, skipping"
    exit 0
fi
cp "$CONF" "$CONF.bak.arch.$(date +%s)"

python3 - "$CONF" << 'PY'
import sys, re
p = sys.argv[1]
with open(p) as f:
    c = f.read()

# Old patterns -> new patterns
# 1. HTTP redirect block
c = c.replace(
    'server_name odoo.clickbulid.com *.clickbulid.com;',
    'server_name odoo.clickbulid.com *.odoo.clickbulid.com;  # patched: tenant subdomain arch')
# 2. HTTPS wildcard server_name regex
c = re.sub(
    r'server_name ~\^\(\?P<sub>\[\^\.\]\+\)\\\.clickbulid\\\.com\$;',
    'server_name ~^(?P<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;',
    c)
# 3. Update the comment header too
c = c.replace(
    '# HTTPS: *.clickbulid.com — tenant subdomains',
    '# HTTPS: *.odoo.clickbulid.com — tenant subdomains (one cert per tenant)')

with open(p, 'w') as f:
    f.write(c)
print('[patch_arch] nginx.conf updated')
PY

echo "[patch_arch] testing nginx config..."
docker exec odoo_saas_nginx nginx -t 2>&1 | grep -vE 'deprecated' | tail -3
echo "[patch_arch] reloading nginx..."
docker exec odoo_saas_nginx nginx -s reload
echo "[patch_arch] done"
