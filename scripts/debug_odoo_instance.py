#!/usr/bin/env python3
"""Debug Odoo instance errors."""
import paramiko
import time
import sys

# Fix Windows console encoding
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

    # Get full logs filtering out non-ASCII-problematic lines
    run(client, "docker logs odoo_roaaa --tail 50 2>&1 | cat", timeout=30)

    print("\n--- ls data dir ---")
    run(client, "ls -la /opt/clickbuild/data/roaaa/")

    print("\n--- container inspect ---")
    run(client, "docker inspect odoo_roaaa --format '{{.State.Status}} {{.State.Health.Status}}'")

    print("\n--- Odoo config check ---")
    run(client, "docker exec odoo_roaaa cat /etc/odoo/odoo.conf 2>/dev/null || docker exec odoo_roaaa cat /opt/odoo/odoo.conf 2>/dev/null || echo 'no config found'")

    print("\n--- Check what Odoo process sees ---")
    run(client, "docker exec odoo_roaaa ls -la /var/lib/odoo/ 2>/dev/null || echo 'cannot exec'")

    print("\n--- Check running processes ---")
    run(client, "docker exec odoo_roaaa ps aux 2>/dev/null | head -20 || echo 'cannot exec'")

    print("\n--- Direct HTTP check ---")
    run(client, "curl -v http://localhost:8100/ 2>&1 | head -30")

    print("\n--- Check if port is listening ---")
    run(client, "ss -tlnp | grep 8100")

    client.close()

if __name__ == "__main__":
    main()
