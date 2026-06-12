#!/usr/bin/env python3
"""Update instance status and verify full routing works."""
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

    # Update instance status using host connection
    print("\n[1] Updating instance status...")
    run(client, """PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "UPDATE instances SET status='running', error_message=NULL WHERE subdomain='roaaa'; SELECT id, subdomain, status, odoo_port FROM instances;" """)

    # Check main nginx config
    print("\n[2] Checking Nginx main config for subdomain routing...")
    run(client, "grep -n 'odoo-proxy\\|subdomain\\|clickbulid' /etc/nginx/sites-available/odoo.clickbulid.com 2>/dev/null | head -20 || ls /etc/nginx/sites-available/")

    run(client, "cat /etc/nginx/sites-available/odoo.clickbulid.com 2>/dev/null | head -80 || cat /etc/nginx/sites-enabled/* 2>/dev/null | head -80")

    # Check if proxy endpoint exists in FastAPI
    print("\n[3] Checking FastAPI proxy endpoint...")
    run(client, "grep -n 'odoo.proxy\\|odoo_proxy\\|subdomain' /opt/clickbuild/backend/app/main.py | head -20")
    run(client, "ls /opt/clickbuild/backend/app/api/v1/endpoints/")

    # Test the API endpoint for instance info
    print("\n[4] Testing API endpoints...")
    run(client, "curl -s http://localhost:8000/api/v1/instances/ | python3 -m json.tool 2>/dev/null | head -30 || curl -s http://localhost:8000/api/v1/instances/ | head -30")
    run(client, "curl -s http://localhost:8000/health 2>/dev/null || curl -s http://localhost:8000/ 2>/dev/null | head -20")

    # Test Odoo directly
    print("\n[5] Odoo direct access test...")
    run(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/web/login 2>/dev/null")
    run(client, "curl -s http://localhost:8100/web/login 2>/dev/null | head -5")

    # Check what port roaaa is on
    print("\n[6] Container port info...")
    run(client, "docker port odoo_roaaa 2>/dev/null")

    # Setup per-instance Nginx if not done via main config catch-all
    print("\n[7] Nginx sites enabled check...")
    run(client, "ls -la /etc/nginx/sites-enabled/")
    run(client, "nginx -t 2>&1")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
