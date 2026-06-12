#!/usr/bin/env python3
"""
Fix instance status to RUNNING and reconfigure Nginx for subdomain routing.
The current Nginx config redirects all *.odoo.clickbulid.com port 80 → HTTPS.
We need to either:
  a) Add HTTPS handler for subdomains (needs wildcard cert - not available yet)
  b) Change port 80 subdomain handling to proxy directly (HTTP for now)
We choose (b) for now — per-instance Nginx direct proxy on port 80.
"""
import paramiko
import time
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def run(client, cmd, timeout=60):
    print(f"\n$ {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(out)
    if err and not out:
        print(f"[stderr] {err}")
    return out, err

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected")

    # ── 1. Fix instance status ────────────────────────────────────────────────
    print("\n[1] Fix instance status to RUNNING...")
    run(client, """PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "UPDATE instances SET status='RUNNING' WHERE subdomain='roaaa'; SELECT subdomain, status, odoo_port FROM instances;" """)

    # ── 2. Modify Nginx to allow HTTP subdomain access ────────────────────────
    print("\n[2] Reading current Nginx config...")
    out, _ = run(client, "cat /etc/nginx/sites-available/clickbuild-platform-ssl")

    # ── 3. Update Nginx config: replace wildcard HTTP→HTTPS redirect with proxy
    print("\n[3] Updating Nginx config...")

    nginx_update = r"""python3 << 'PYEOF'
path = '/etc/nginx/sites-available/clickbuild-platform-ssl'
with open(path) as f:
    content = f.read()

# Replace the blanket HTTP redirect for subdomains with a direct proxy
OLD = '''server {
    listen 80;
    server_name ~^.+\\.odoo\\.clickbulid\\.com$;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}'''

NEW = '''# HTTP subdomain proxy — direct to FastAPI odoo-proxy (no HTTPS redirect yet, wildcard cert pending)
server {
    listen 80;
    server_name ~^(?<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;

    location /.well-known/acme-challenge/ { root /var/www/html; }

    location / {
        proxy_pass         http://127.0.0.1:8000/odoo-proxy/;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Odoo-Subdomain  $sub;
        proxy_buffering    off;
        proxy_read_timeout 300s;
        client_max_body_size 100M;
    }
}'''

if OLD in content:
    content = content.replace(OLD, NEW)
    with open(path, 'w') as f:
        f.write(content)
    print("OK: updated wildcard block")
else:
    # Try without escaped dots
    import re
    pattern = r'server \{\n    listen 80;\n    server_name ~\^\.?\+\\\.odoo\\\.clickbulid\\\.com\$;\n.*?\n\}'
    if re.search(r'server_name ~\^\.', content):
        print("Found pattern with regex, manual edit needed")
        # Show the relevant section
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'clickbulid.com$' in line and '80' in content[max(0,content.index(line)-100):content.index(line)+100]:
                start = max(0, i-3)
                for j in range(start, min(len(lines), i+8)):
                    print(f"  {j}: {lines[j]}")
    else:
        print("Pattern not found in Nginx config")
        print("Current content around subdomain server block:")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'clickbulid' in line:
                start = max(0, i-2)
                for j in range(start, min(len(lines), i+5)):
                    print(f"  {j}: {lines[j]}")
PYEOF"""

    run(client, nginx_update, timeout=30)

    # ── 4. Test and reload Nginx ──────────────────────────────────────────────
    out, err = run(client, "nginx -t 2>&1")
    if 'successful' in out or 'successful' in err:
        run(client, "systemctl reload nginx")
        print("  Nginx reloaded!")
    else:
        print(f"  Nginx test failed — check config")

    # ── 5. Remove my separate odoo-instances symlink (now handled in main config)
    run(client, "rm -f /etc/nginx/sites-enabled/odoo-instances 2>/dev/null; nginx -t 2>&1 && systemctl reload nginx")

    # ── 6. Test proxy now ─────────────────────────────────────────────────────
    print("\n[4] Testing proxy after fix...")
    time.sleep(2)
    run(client, "curl -s -o /dev/null -w '%{http_code}' -H 'X-Odoo-Subdomain: roaaa' http://localhost:8000/odoo-proxy/web/login 2>/dev/null")
    run(client, "curl -v -L --max-redirs 3 http://roaaa.odoo.clickbulid.com/web/login 2>&1 | head -30")

    # ── 7. Fix proxy.py to forward path properly ──────────────────────────────
    print("\n[5] Checking proxy.py full content...")
    run(client, "cat /opt/clickbuild/backend/app/api/v1/endpoints/proxy.py")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
