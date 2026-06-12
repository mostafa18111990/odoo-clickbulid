#!/usr/bin/env python3
"""Fix Odoo volume mounts and permissions properly."""
import paramiko
import time
import sys
import json

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

    # Check actual volume mounts of the container
    print("\n=== CONTAINER MOUNTS ===")
    run(client, "docker inspect odoo_roaaa --format '{{json .Mounts}}' | python3 -m json.tool")

    # Check the actual environment
    print("\n=== CONTAINER ENV ===")
    run(client, "docker inspect odoo_roaaa --format '{{json .Config.Env}}' | python3 -m json.tool")

    # Check how the container was created (HostConfig)
    print("\n=== HOST CONFIG BINDS ===")
    run(client, "docker inspect odoo_roaaa --format '{{json .HostConfig.Binds}}' | python3 -m json.tool")

    # Try to write into the sessions dir inside the container directly
    print("\n=== TRY FIX SESSIONS DIR INSIDE CONTAINER ===")
    run(client, "docker exec -u root odoo_roaaa mkdir -p /var/lib/odoo/sessions && docker exec -u root odoo_roaaa chown -R odoo:odoo /var/lib/odoo && docker exec -u root odoo_roaaa chmod 700 /var/lib/odoo/sessions")

    # Also create log dir if missing
    run(client, "docker exec -u root odoo_roaaa mkdir -p /var/log/odoo && docker exec -u root odoo_roaaa chown -R odoo:odoo /var/log/odoo")

    # Now kill the main odoo process to trigger restart (container stays up due to entrypoint)
    print("\n=== RESTARTING ODOO PROCESS ===")
    run(client, "docker exec odoo_roaaa kill 1 2>/dev/null; sleep 2; docker restart odoo_roaaa")
    print("Waiting 25s...")
    time.sleep(25)

    # Check health
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/web/health 2>/dev/null || curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/ 2>/dev/null")
    print(f"\nHTTP status: {out}")

    # Get fresh logs
    run(client, "docker logs odoo_roaaa --tail 30 2>&1 | cat")

    # ── Fix provisioning.py to always create sessions dir inside container ──
    print("\n=== UPDATING PROVISIONING.PY ===")

    fix_prov = r"""python3 << 'PYEOF'
import re

path = '/opt/clickbuild/backend/app/services/provisioning.py'
with open(path) as f:
    content = f.read()

print("File length:", len(content))
print("Has containers.run:", 'containers.run' in content)
print("Has client.containers:", 'client.containers' in content)

# Find the containers.run call
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'containers.run' in line or '.containers.run' in line:
        start = max(0, i-5)
        end = min(len(lines), i+10)
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}")
        print("---")
PYEOF"""

    run(client, fix_prov, timeout=30)

    client.close()

if __name__ == "__main__":
    main()
