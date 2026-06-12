#!/usr/bin/env python
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"

# Fix ALLOWED_ORIGINS to JSON array format
stdin, stdout, stderr = client.exec_command("cat /opt/clickbuild/backend/.env")
env = stdout.read().decode('utf-8', errors='replace')

env_new = ""
for line in env.splitlines():
    if line.startswith("ALLOWED_ORIGINS="):
        env_new += f'ALLOWED_ORIGINS=["https://{DOMAIN}","http://129.121.98.243"]\n'
    else:
        env_new += line + "\n"

sftp.putfo(io.BytesIO(env_new.encode()), '/opt/clickbuild/backend/.env')
sftp.close()
print("[OK] Fixed ALLOWED_ORIGINS in .env")

# Restart backend
stdin, stdout, stderr = client.exec_command(
    "systemctl restart clickbuild-api && sleep 4 && "
    "curl -s http://127.0.0.1:8000/api/health"
)
out = stdout.read().decode('utf-8', errors='replace')
print(f"Backend health: {out.strip()}")

# Test HTTPS
time.sleep(1)
stdin, stdout, stderr = client.exec_command(
    f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health"
)
code = stdout.read().decode().strip()
print(f"HTTPS API: HTTP {code}")

if code == '200':
    print(f"\nAll systems GO!")
    print(f"  https://{DOMAIN}")
    print(f"  https://{DOMAIN}/ar/register")
    print(f"  https://{DOMAIN}/ar/login")
else:
    # Show what nginx is doing
    stdin, stdout, stderr = client.exec_command(
        f"curl -skv https://{DOMAIN}/api/health 2>&1 | grep -E 'HTTP|< |connected' | head -10"
    )
    print(stdout.read().decode())

client.close()
