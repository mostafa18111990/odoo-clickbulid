#!/usr/bin/env python3
import paramiko, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    return c

def run(c, cmd, timeout=60):
    print(f"\n$ {cmd[:120]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out[:2000])
    if err and not out: print(f"[err] {err[:500]}")
    return out, err

def upload(c, path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

def main():
    c = connect()
    print("Connected — diagnosing 502...")

    # ── 1. Check all services ────────────────────────────────────────────────
    print("\n[1] Service status...")
    run(c, "systemctl is-active clickbuild-api clickbuild-worker | paste - -")
    run(c, "docker ps --format '{{.Names}}\t{{.Status}}' 2>/dev/null")
    run(c, "pm2 list 2>/dev/null | grep clickbuild")

    # ── 2. Check FastAPI directly ────────────────────────────────────────────
    print("\n[2] FastAPI health...")
    out, _ = run(c, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ 2>/dev/null")
    print(f"  FastAPI port 8000: {out}")

    # ── 3. Check proxy with correct header ──────────────────────────────────
    print("\n[3] Testing FastAPI proxy endpoint...")
    out, _ = run(c, "curl -s -o /dev/null -w '%{http_code}' -H 'X-Odoo-Subdomain: roaaa' http://127.0.0.1:8000/odoo-proxy/web/login 2>/dev/null")
    print(f"  Proxy with header: {out}")

    # ── 4. Check Odoo container directly ────────────────────────────────────
    print("\n[4] Odoo direct access...")
    out, _ = run(c, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8100/web/login 2>/dev/null")
    print(f"  Odoo port 8100: {out}")

    # ── 5. Check roaaa nginx conf ────────────────────────────────────────────
    print("\n[5] Nginx config for roaaa...")
    run(c, "cat /etc/nginx/sites-available/instances/roaaa.conf")

    # ── 6. Check nginx error log ─────────────────────────────────────────────
    print("\n[6] Nginx error log (last 20 lines)...")
    run(c, "tail -20 /var/log/nginx/error.log 2>/dev/null")

    # ── 7. Check FastAPI logs ────────────────────────────────────────────────
    print("\n[7] FastAPI logs...")
    run(c, "journalctl -u clickbuild-api -n 30 --no-pager 2>/dev/null | tail -20")

    # ── 8. The real test — simulate what nginx does ──────────────────────────
    print("\n[8] Simulating nginx request to FastAPI proxy...")
    out, _ = run(c, (
        "curl -v "
        "-H 'Host: roaaa.odoo.clickbulid.com' "
        "-H 'X-Odoo-Subdomain: roaaa' "
        "-H 'X-Forwarded-Proto: https' "
        "http://127.0.0.1:8000/odoo-proxy/web/login 2>&1 | head -40"
    ))

    c.close()

if __name__ == "__main__":
    main()
