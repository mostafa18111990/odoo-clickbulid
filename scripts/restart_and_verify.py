#!/usr/bin/env python3
import paramiko, time, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

def run(c, cmd, timeout=60):
    print(f"\n$ {cmd[:100]}")
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out: print(out[:500])
    if err and not out: print(f"[err] {err[:200]}")
    return out, err

def main():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected")

    # Hard restart PM2 — delete and re-add
    run(c, "pm2 delete clickbuild-frontend 2>/dev/null; sleep 1")
    run(c, "cd /opt/clickbuild/frontend && pm2 start npm --name clickbuild-frontend -- start -- -p 3000")
    print("Waiting 8s for Next.js to start...")
    time.sleep(8)

    run(c, "pm2 status 2>/dev/null | grep clickbuild")

    print("\nVerifying new pages:")
    for path in ['/ar/', '/ar/admin/ops', '/ar/admin/sre', '/ar/admin/compliance', '/ar/support', '/ar/admin/support-queue']:
        out, _ = run(c, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:3000{path} 2>/dev/null")
        ok = out in ['200','307','301','302','308']
        print(f"  [{'OK' if ok else 'FAIL'}] {path}: {out}")

    # Final full platform check
    print("\nFull platform status:")
    run(c, "systemctl is-active clickbuild-api clickbuild-worker clickbuild-beat | paste - - -")
    run(c, "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null | grep -v NAMES")
    run(c, 'PGPASSWORD="CB_pg_S3cur3_2024!" psql -h 127.0.0.1 -U clickbuild clickbuild_platform -c "SELECT (SELECT COUNT(*) FROM slo_definitions) slos, (SELECT COUNT(*) FROM compliance_checks) controls, (SELECT COUNT(*) FROM runbooks) runbooks, (SELECT COUNT(*) FROM support_tickets) tickets, (SELECT COUNT(*) FROM audit_logs) audit_events;"')

    c.close()

if __name__ == "__main__":
    main()
