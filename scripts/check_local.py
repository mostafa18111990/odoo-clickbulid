#!/usr/bin/env python
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    "find /opt/clickbuild/backend/app -name '*.py' | grep -v __pycache__ | grep -v venv | sort",
    "cat /opt/clickbuild/backend/app/services/provisioning.py",
    "cat /opt/clickbuild/backend/app/services/nginx_service.py 2>/dev/null || echo NOT_FOUND",
    "cat /opt/clickbuild/backend/app/main.py",
    "cat /opt/clickbuild/backend/app/models/user.py",
]
for cmd in cmds:
    print(f"\n{'='*70}\n$ {cmd[:80]}\n{'='*70}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))
client.close()
