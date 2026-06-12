#!/bin/bash
# Inject the /web/database/* block into every existing per-tenant
# nginx config so legacy tenants get the same protection as new ones.
# Idempotent.
set -e
TENANTS_DIR=/opt/odoo-saas/nginx-tenants
INJECT='    # Customers must never reach Odoo'"'"'s master-password database creator.
    location ~ ^/web/database/ {
        return 404;
    }
'

count=0
for f in "$TENANTS_DIR"/*.conf; do
    [ -f "$f" ] || continue
    if grep -q "location ~ \^/web/database/" "$f"; then
        continue
    fi
    # Inject right after the `proxy_send_timeout` line.
    python3 - "$f" "$INJECT" << 'PY'
import sys
path, snippet = sys.argv[1], sys.argv[2]
with open(path) as f: c = f.read()
anchor = '    proxy_send_timeout 720s;\n'
if anchor in c:
    c = c.replace(anchor, anchor + '\n' + snippet, 1)
    with open(path, 'w') as f: f.write(c)
    print(f'  patched {path}')
else:
    print(f'  SKIP {path} — anchor not found')
PY
    count=$((count + 1))
done

echo "[patch] processed tenants"
docker exec odoo_saas_nginx nginx -t 2>&1 | grep -vE 'deprecated' | tail -2
docker exec odoo_saas_nginx nginx -s reload
echo "[patch] reloaded"
