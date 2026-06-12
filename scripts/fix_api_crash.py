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
    if out: print(out[:3000])
    if err and not out: print(f"[err] {err[:1000]}")
    return out, err

def upload(c, path, content):
    sftp = c.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  -> {path}")

def main():
    c = connect()

    # ── 1. See actual error ──────────────────────────────────────────────────
    print("\n[1] What port 8000 says...")
    run(c, "ss -tlnp | grep 8000 || echo 'Nothing on 8000'")

    print("\n[2] Full journalctl for clickbuild-api...")
    run(c, "journalctl -u clickbuild-api --no-pager -n 50 2>/dev/null | grep -v 'Stopping\\|Stopped\\|Consumed' | tail -30")

    print("\n[3] Run uvicorn manually to see the real error...")
    out, err = run(c,
        "cd /opt/clickbuild/backend && "
        "source venv/bin/activate 2>/dev/null || true && "
        "timeout 10 python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 | head -40",
        timeout=20
    )

    # ── 2. Identify import errors ────────────────────────────────────────────
    print("\n[4] Checking for import errors directly...")
    run(c,
        "cd /opt/clickbuild/backend && "
        "source venv/bin/activate 2>/dev/null || true && "
        "python -c 'from app.main import app; print(\"Import OK\")' 2>&1",
        timeout=30
    )

    # ── 3. Fix common issues ─────────────────────────────────────────────────
    print("\n[5] Checking main.py...")
    run(c, "cat /opt/clickbuild/backend/app/main.py")

    print("\n[6] Check each new module imports...")
    for mod in ['sre', 'support', 'compliance', 'contractors']:
        out, _ = run(c,
            f"cd /opt/clickbuild/backend && "
            f"source venv/bin/activate 2>/dev/null || true && "
            f"python -c 'from app.api.v1.endpoints.{mod} import router; print(\"{mod}: OK\")' 2>&1"
        )

    # Check middleware
    run(c,
        "cd /opt/clickbuild/backend && "
        "source venv/bin/activate 2>/dev/null || true && "
        "python -c 'from app.middleware.audit import AuditLogMiddleware; print(\"audit: OK\")' 2>&1"
    )

    # Check services
    for svc in ['sre', 'support']:
        run(c,
            f"cd /opt/clickbuild/backend && "
            f"source venv/bin/activate 2>/dev/null || true && "
            f"python -c 'from app.services.{svc} import *; print(\"{svc}: OK\")' 2>&1"
        )

    c.close()

if __name__ == "__main__":
    main()
