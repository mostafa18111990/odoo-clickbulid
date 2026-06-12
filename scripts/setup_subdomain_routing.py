#!/usr/bin/env python3
"""Setup subdomain routing and fix instance status."""
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

NGINX_SUBDOMAIN_CONF = """\
# ──────────────────────────────────────────────────────────────────────────────
# Wildcard catch-all for *.odoo.clickbulid.com  →  FastAPI odoo-proxy
# ──────────────────────────────────────────────────────────────────────────────
server {
    listen 80;
    server_name ~^(?<sub>[^.]+)\\.odoo\\.clickbulid\\.com$;

    # Pass to FastAPI proxy — it reads X-Odoo-Subdomain to find the right port
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
}
"""

NGINX_DIRECT_CONF = """\
# ──────────────────────────────────────────────────────────────────────────────
# Direct Nginx proxy for roaaa.odoo.clickbulid.com → port 8100
# (used when FastAPI proxy is bypassed for performance)
# ──────────────────────────────────────────────────────────────────────────────
server {
    listen 80;
    server_name roaaa.odoo.clickbulid.com;

    location / {
        proxy_pass         http://127.0.0.1:8100;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        proxy_buffering    off;
        proxy_read_timeout 300s;
        client_max_body_size 100M;
    }
}
"""

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected")

    # Check enum values
    print("\n[1] Checking instancestatus enum values...")
    run(client, """PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "SELECT unnest(enum_range(NULL::instancestatus));" """)

    # Check current instance record
    run(client, """PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "SELECT id, subdomain, status, odoo_port, error_message FROM instances;" """)

    # Update status to correct enum value
    print("\n[2] Updating instance status...")
    # Try common enum values
    for status in ['active', 'running', 'ACTIVE', 'RUNNING']:
        out, err = run(client, f"""PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "UPDATE instances SET status='{status}', error_message=NULL WHERE subdomain='roaaa';" 2>&1""")
        if 'ERROR' not in out and 'ERROR' not in err:
            print(f"  Status '{status}' worked!")
            break

    # Check current Nginx main config
    print("\n[3] Checking current Nginx config...")
    run(client, "cat /etc/nginx/sites-available/clickbuild-platform-ssl 2>/dev/null | head -60")

    # Write wildcard subdomain config
    print("\n[4] Writing wildcard subdomain config...")
    sftp = client.open_sftp()

    # Write the subdomain wildcard config
    with sftp.open('/etc/nginx/sites-available/odoo-instances', 'w') as f:
        f.write(NGINX_SUBDOMAIN_CONF)
    print("  Wrote /etc/nginx/sites-available/odoo-instances")

    # Write direct proxy config for roaaa
    with sftp.open('/etc/nginx/sites-available/instances/roaaa.conf', 'w') as f:
        f.write(NGINX_DIRECT_CONF)
    print("  Wrote instances/roaaa.conf")
    sftp.close()

    # Enable the wildcard config
    run(client, "ln -sf /etc/nginx/sites-available/odoo-instances /etc/nginx/sites-enabled/odoo-instances 2>/dev/null || true")

    # Test and reload Nginx
    out, err = run(client, "nginx -t 2>&1")
    if 'successful' in out or 'successful' in err:
        run(client, "systemctl reload nginx")
        print("  Nginx reloaded successfully!")
    else:
        print(f"  Nginx test failed: {out} {err}")

    # Check proxy.py to understand how it works
    print("\n[5] Checking proxy.py...")
    run(client, "cat /opt/clickbuild/backend/app/api/v1/endpoints/proxy.py | head -60")

    # Test subdomain routing via curl (simulating what browser does)
    print("\n[6] Testing proxy endpoint...")
    run(client, "curl -s -o /dev/null -w '%{http_code}' -H 'X-Odoo-Subdomain: roaaa' http://localhost:8000/odoo-proxy/ 2>/dev/null")
    run(client, "curl -s -H 'X-Odoo-Subdomain: roaaa' http://localhost:8000/odoo-proxy/web/login 2>/dev/null | head -5")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
