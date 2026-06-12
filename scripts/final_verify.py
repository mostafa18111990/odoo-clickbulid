#!/usr/bin/env python3
"""Full end-to-end platform verification."""
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
    if out: print(out)
    if err and not out: print(f"[stderr] {err}")
    return out, err

def check(label, code, expected=["200","303","301","302"]):
    ok = any(e in code for e in expected)
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {label}: HTTP {code}")
    return ok

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("=" * 60)
    print("CLICKBUILD PLATFORM — FINAL VERIFICATION")
    print("=" * 60)

    results = []

    # 1. Main platform HTTPS
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' https://odoo.clickbulid.com/ 2>/dev/null")
    results.append(check("Main platform (HTTPS)", out))

    # 2. API health
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' https://odoo.clickbulid.com/api/v1/plans/ 2>/dev/null")
    results.append(check("Plans API", out))

    # 3. Odoo instance direct
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/web/login 2>/dev/null")
    results.append(check("Odoo direct (port 8100)", out))

    # 4. Subdomain proxy HTTP
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' http://roaaa.odoo.clickbulid.com/web/login 2>/dev/null")
    results.append(check("Subdomain proxy (HTTP)", out))

    # 5. FastAPI proxy
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' -H 'X-Odoo-Subdomain: roaaa' http://localhost:8000/odoo-proxy/web/login 2>/dev/null")
    results.append(check("FastAPI proxy endpoint", out))

    # 6. Services status
    print("\n--- Services ---")
    run(client, "systemctl is-active clickbuild-api clickbuild-worker clickbuild-beat | paste - - -")
    run(client, "pm2 list 2>/dev/null | grep clickbuild || echo 'pm2 not responding'")
    run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -v '^NAMES'")

    # 7. DB state
    print("\n--- Database ---")
    run(client, """PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "SELECT subdomain, status, odoo_port, is_trial FROM instances; SELECT COUNT(*) as plans FROM plans; SELECT COUNT(*) as users FROM users;" """)

    # Summary
    passed = sum(results)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"RESULT: {passed}/{total} checks passed")
    if passed == total:
        print("Platform is fully operational!")
    else:
        print("Some checks failed — review above")
    print("=" * 60)

    client.close()

if __name__ == "__main__":
    main()
