#!/bin/bash
# Block public access to /web/database/* (Odoo's master-password database
# creator/selector). It MUST never be reachable from a tenant subdomain,
# a bare IP, or anywhere except the master "odoo.clickbulid.com" host.
# Idempotent.
set -e
CONF=/opt/odoo-saas/config/nginx.conf
MARKER='# block-db-manager: blocked'
if grep -q "$MARKER" "$CONF"; then
    echo "[block_db] already patched, skipping"
    exit 0
fi
cp "$CONF" "$CONF.bak.blockdb.$(date +%s)"

python3 - "$CONF" << 'PY'
import sys, re
p = sys.argv[1]
with open(p) as f:
    c = f.read()

# Block /web/database/* on every server block EXCEPT the master
# "odoo.clickbulid.com" one. Strategy: walk through every `server {`
# block, and if its server_name is NOT "odoo.clickbulid.com" exactly,
# inject a `location ~ ^/web/database/` 410 Gone rule at the top of the
# location list.
inject = '''        location ~ ^/web/database/ {
            # block-db-manager: blocked — database manager not exposed publicly
            return 404;
        }
'''
out = []
i = 0
n = len(c)
while i < n:
    m = re.search(r'(\n {4}server \{[^\n]*\n)', c[i:])
    if not m:
        out.append(c[i:])
        break
    # Find the matching closing brace by tracking braces.
    start = i + m.start(1)
    out.append(c[i:start])
    # Read server body
    j = start
    depth = 0
    body_start = None
    for k in range(start, n):
        ch = c[k]
        if ch == '{':
            depth += 1
            if depth == 1:
                body_start = k + 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                j = k + 1
                break
    body = c[body_start:j-1] if body_start else ''
    sn = re.search(r'server_name ([^;]+);', body)
    is_master = bool(sn and 'odoo.clickbulid.com' in sn.group(1)
                     and '*.odoo.clickbulid.com' not in sn.group(1)
                     and '~' not in sn.group(1))
    if is_master:
        # Leave master server block untouched.
        out.append(c[start:j])
    else:
        # Inject the block-db rule right after the `{`.
        out.append(c[start:body_start] + '\n' + inject + c[body_start:j])
    i = j

new = ''.join(out)
with open(p, 'w') as f:
    f.write(new)
print('[block_db] patched: /web/database/* now blocked except on master host')
PY

echo "[block_db] testing nginx..."
docker exec odoo_saas_nginx nginx -t 2>&1 | grep -vE 'deprecated' | tail -3
echo "[block_db] reloading..."
docker exec odoo_saas_nginx nginx -s reload
echo "[block_db] done"
