#!/usr/bin/env python
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    "cat /opt/clickbuild/frontend/.env.local 2>/dev/null || cat /opt/clickbuild/frontend/.env 2>/dev/null || echo 'NO ENV FILE'",
    "curl -s http://127.0.0.1/api/health",
    "curl -s http://127.0.0.1/api/v1/auth/register -X POST -H 'Content-Type: application/json' -d '{\"email\":\"test@t.com\",\"password\":\"TestPass1\",\"name\":\"Test\",\"country\":\"EG\",\"language\":\"ar\"}' 2>&1",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode('utf-8', errors='replace'))
client.close()
