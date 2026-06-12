#!/usr/bin/env python
"""Check backend structure on server"""
import paramiko
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    "find /opt/clickbuild/backend -name '*.py' | head -50",
    "cat /opt/clickbuild/backend/app/main.py 2>/dev/null | head -30",
    "cat /opt/clickbuild/backend/app/db/base.py 2>/dev/null || echo NO_BASE",
    "ls /opt/clickbuild/backend/app/models/ 2>/dev/null || echo NO_MODELS",
]

for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
