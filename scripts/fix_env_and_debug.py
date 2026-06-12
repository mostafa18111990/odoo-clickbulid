#!/usr/bin/env python
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

# Fix .env.local to use IP instead of domain
new_env = """\
NEXT_PUBLIC_API_URL=http://129.121.98.243/api/v1
NEXT_PUBLIC_DOMAIN=129.121.98.243
"""
sftp = client.open_sftp()
sftp.putfo(io.BytesIO(new_env.encode()), '/opt/clickbuild/frontend/.env.local')
sftp.close()
print("[OK] Fixed .env.local")

# Check the FastAPI error
cmds = [
    # Test register directly on FastAPI port (bypassing nginx)
    "curl -s http://127.0.0.1:8000/api/v1/auth/register -X POST -H 'Content-Type: application/json' -d '{\"email\":\"test99@t.com\",\"password\":\"TestPass1\",\"name\":\"Test\",\"country\":\"EG\",\"language\":\"ar\"}'",
    # Check FastAPI logs
    "journalctl -u clickbuild-api -n 30 --no-pager 2>&1 | tail -30",
    # Check if email_service is causing issues
    "cat /opt/clickbuild/backend/app/services/email_service.py | head -30",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
