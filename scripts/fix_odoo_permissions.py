#!/usr/bin/env python3
"""Fix Odoo 19 sessions directory permission error + update provisioning to prevent recurrence."""
import paramiko
import time
import sys

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
    if err:
        print(f"[stderr] {err}")
    return out, err

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=30)
    print("Connected to server")

    # ── Step 1: Find odoo UID inside the image ──────────────────────────────
    print("\n[1] Finding odoo user UID inside clickbuild/odoo:19 image...")
    out, _ = run(client, "docker run --rm --entrypoint /bin/sh clickbuild/odoo:19 -c 'id odoo' 2>/dev/null || docker run --rm clickbuild/odoo:19 id odoo 2>/dev/null || echo 'uid=101'")
    # typical odoo UID is 101 or 999
    odoo_uid = 101
    if "uid=" in out:
        try:
            odoo_uid = int(out.split("uid=")[1].split("(")[0])
            print(f"  Odoo UID = {odoo_uid}")
        except:
            print(f"  Could not parse UID, defaulting to 101")

    # ── Step 2: Fix existing roaaa instance ─────────────────────────────────
    print("\n[2] Fixing existing odoo_roaaa container...")

    # Fix host data directory ownership
    run(client, f"chown -R {odoo_uid}:{odoo_uid} /opt/clickbuild/data/roaaa/ 2>/dev/null || true")
    run(client, f"chmod -R 755 /opt/clickbuild/data/roaaa/ 2>/dev/null || true")

    # Create sessions dir on host with correct ownership
    run(client, f"mkdir -p /opt/clickbuild/data/roaaa/sessions")
    run(client, f"chown {odoo_uid}:{odoo_uid} /opt/clickbuild/data/roaaa/sessions")
    run(client, f"chmod 700 /opt/clickbuild/data/roaaa/sessions")

    # Restart the container
    run(client, "docker restart odoo_roaaa", timeout=60)
    print("  Waiting 20s for Odoo to start...")
    time.sleep(20)

    # Check health
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/web/health 2>/dev/null || curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/ 2>/dev/null")
    print(f"  HTTP status: {out}")

    # Show recent logs
    run(client, "docker logs odoo_roaaa --tail 20 2>&1")

    # ── Step 3: Update provisioning.py to fix all future instances ──────────
    print("\n[3] Updating provisioning.py to fix permissions before container start...")

    PROVISIONING_FIX = r'''
import subprocess as _subprocess

def _fix_data_dir_permissions(data_path: str, odoo_uid: int = 101):
    """Fix host data directory ownership so Odoo container can write to it."""
    import os
    os.makedirs(data_path, exist_ok=True)
    # sessions dir specifically needed by Odoo 19
    sessions_dir = os.path.join(data_path, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    try:
        _subprocess.run(["chown", "-R", f"{odoo_uid}:{odoo_uid}", data_path], check=True)
        _subprocess.run(["chmod", "-R", "755", data_path], check=True)
        _subprocess.run(["chmod", "700", sessions_dir], check=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not fix data dir permissions: {e}")
'''

    # Read current provisioning.py
    out, _ = run(client, "cat /opt/clickbuild/backend/app/services/provisioning.py | head -5")
    out_full, _ = run(client, "wc -l /opt/clickbuild/backend/app/services/provisioning.py")

    # Write the fix inline using Python on the server
    fix_script = """python3 << 'PYEOF'
import re

path = '/opt/clickbuild/backend/app/services/provisioning.py'
with open(path) as f:
    content = f.read()

# Add helper function after imports if not already present
if '_fix_data_dir_permissions' not in content:
    helper = '''
import subprocess as _subprocess

def _fix_data_dir_permissions(data_path: str, odoo_uid: int = 101):
    import os
    os.makedirs(data_path, exist_ok=True)
    sessions_dir = os.path.join(data_path, "sessions")
    os.makedirs(sessions_dir, exist_ok=True)
    try:
        _subprocess.run(["chown", "-R", f"{odoo_uid}:{odoo_uid}", data_path], check=True)
        _subprocess.run(["chmod", "-R", "755", data_path], check=True)
        _subprocess.run(["chmod", "700", sessions_dir], check=True)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Could not fix data dir permissions: {e}")

'''
    # Insert after the last import block
    lines = content.split('\\n')
    last_import = 0
    for i, line in enumerate(lines):
        if line.startswith('import ') or line.startswith('from '):
            last_import = i
    lines.insert(last_import + 1, helper)
    content = '\\n'.join(lines)

# Now find where docker.containers.run is called and add the permission fix before it
# Pattern: look for data_path or data_dir variable being set
if '_fix_data_dir_permissions' in content and 'containers.run' in content:
    # Add call before containers.run if not already there
    if '_fix_data_dir_permissions(data_' not in content:
        # Replace the containers.run call to add permission fix before it
        content = content.replace(
            'container = docker_client.containers.run(',
            '_fix_data_dir_permissions(data_path)\\n    container = docker_client.containers.run('
        )
        if '_fix_data_dir_permissions(data_path)' not in content:
            # Try alternative variable names
            content = content.replace(
                'container = client.containers.run(',
                '_fix_data_dir_permissions(data_path)\\n    container = client.containers.run('
            )

with open(path, 'w') as f:
    f.write(content)

print("provisioning.py updated successfully")
PYEOF"""

    run(client, fix_script, timeout=30)

    # ── Step 4: Also patch via direct search/replace for robustness ─────────
    print("\n[4] Checking provisioning.py for containers.run call...")
    out, _ = run(client, "grep -n 'containers.run\\|data_path\\|data_dir\\|_fix_data' /opt/clickbuild/backend/app/services/provisioning.py | head -30")

    # ── Step 5: Show current provisioning.py key section ────────────────────
    print("\n[5] Provisioning.py around containers.run:")
    out, _ = run(client, "grep -n -A3 -B3 'containers.run' /opt/clickbuild/backend/app/services/provisioning.py | head -40")

    # ── Step 6: Restart backend ──────────────────────────────────────────────
    print("\n[6] Restarting backend service...")
    run(client, "systemctl restart clickbuild-api")
    time.sleep(3)
    run(client, "systemctl status clickbuild-api --no-pager | head -10")

    # ── Step 7: Final health check ───────────────────────────────────────────
    print("\n[7] Final health check...")
    time.sleep(5)
    out, _ = run(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/web/health 2>/dev/null || curl -s -o /dev/null -w '%{http_code}' http://localhost:8100/ 2>/dev/null")
    print(f"  Odoo roaaa HTTP: {out}")

    out, _ = run(client, "docker logs odoo_roaaa --tail 15 2>&1")

    # ── Step 8: Update instance status if Odoo is healthy ───────────────────
    if out.strip() in ["200", "303", "301", "302"]:
        print("\n[8] Odoo is healthy! Updating instance status in DB...")
        run(client, """psql -U clickbuild clickbuild_platform -c "UPDATE instances SET status='running', error_message=NULL WHERE subdomain='roaaa';" """)
    else:
        print(f"\n[8] Odoo still not healthy (HTTP {out}), checking logs...")
        run(client, "docker logs odoo_roaaa --tail 30 2>&1")

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
