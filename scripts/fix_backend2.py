#!/usr/bin/env python
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

DOMAIN = "odoo.clickbulid.com"

# Check what's in .env and what format ALLOWED_ORIGINS needs
cmds = [
    "cat /opt/clickbuild/backend/.env | grep -v PASSWORD | grep -v SECRET",
    "cat /opt/clickbuild/backend/app/core/config.py | grep -A5 'ALLOWED_ORIGINS'",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode('utf-8', errors='replace'))

# Try running uvicorn manually to see the actual error
print("\n=== Manual uvicorn test ===")
test_cmd = (
    "cd /opt/clickbuild/backend && source venv/bin/activate && "
    "timeout 8 uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 | head -20"
)
stdin, stdout, stderr = client.exec_command(test_cmd, timeout=20)
out = stdout.read().decode('utf-8', errors='replace')
print(out)

client.close()
