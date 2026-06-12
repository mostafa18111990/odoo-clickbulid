#!/bin/bash
# Idempotent patch — adds an internal monitoring server block to nginx.conf
# Run on the server. Safe to re-run: skips if marker already present.
set -e
CONF=/opt/odoo-saas/config/nginx.conf
MARKER="# --- INTERNAL: monitoring scraper endpoint ---"
if grep -q "$MARKER" "$CONF"; then
    echo "[patch_nginx_monitoring] marker present, skipping"
    exit 0
fi
cp "$CONF" "$CONF.bak.$(date +%s)"
# Insert the block right before the final } that closes http {}
python3 - "$CONF" << 'PY'
import sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
block = '''
    # --- INTERNAL: monitoring scraper endpoint ---
    # Listens on port 81. Forces Host = odoo.clickbulid.com so Odoo dbfilter
    # routes to DB "odoo". Restricted to private/docker networks only.
    server {
        listen 81;
        server_name _;
        allow 127.0.0.0/8;
        allow 172.16.0.0/12;
        allow 10.0.0.0/8;
        deny all;
        location ~ ^/(healthz|readyz|metrics)$ {
            proxy_pass http://odoo_backend;
            proxy_set_header Host odoo.clickbulid.com;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-Proto https;
            proxy_read_timeout 30s;
        }
    }
'''
stripped = content.rstrip()
assert stripped.endswith('}'), 'unexpected end of nginx.conf'
new = stripped[:-1] + block + '\n}\n'
with open(path, 'w') as f:
    f.write(new)
print('[patch_nginx_monitoring] inserted block, new lines:', new.count('\n'))
PY
echo "[patch_nginx_monitoring] testing config..."
docker exec odoo_saas_nginx nginx -t
echo "[patch_nginx_monitoring] reloading nginx..."
docker exec odoo_saas_nginx nginx -s reload
echo "[patch_nginx_monitoring] done"
