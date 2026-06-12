#!/bin/bash
# Add stronger security headers to nginx.conf. Idempotent.
set -e
CONF=/opt/odoo-saas/config/nginx.conf
MARKER="# --- security headers (auto-added) ---"
if grep -q "$MARKER" "$CONF"; then
    echo "[security_headers] marker present, skipping"
    exit 0
fi
cp "$CONF" "$CONF.bak.headers.$(date +%s)"

# Insert a shared snippet that we then include in each HTTPS server block.
# Simpler: just patch the existing HSTS line to add the extra headers next to it.
# We add them after the existing 'add_header Strict-Transport-Security' line.

python3 - "$CONF" << 'PY'
import sys, re
path = sys.argv[1]
with open(path) as f:
    content = f.read()

marker = '        # --- security headers (auto-added) ---'
extra = '''
        # --- security headers (auto-added) ---
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;
        add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
        add_header X-XSS-Protection "1; mode=block" always;'''

# Inject right after every "Strict-Transport-Security" header line (HTTPS blocks only).
def inject(m):
    line = m.group(0)
    return line + extra

new = re.sub(r'add_header Strict-Transport-Security[^;]*;', inject, content)
if new == content:
    print('FAIL: no HSTS line to attach after')
    sys.exit(1)
with open(path, 'w') as f:
    f.write(new)
print('[security_headers] injected after', new.count(extra.strip()), 'HSTS line(s)')
PY

echo "[security_headers] testing nginx config..."
docker exec odoo_saas_nginx nginx -t
echo "[security_headers] reloading..."
docker exec odoo_saas_nginx nginx -s reload
echo "[security_headers] done"
