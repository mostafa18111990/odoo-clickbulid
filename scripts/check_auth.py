#!/usr/bin/env python
"""Check auth endpoints and frontend structure"""
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
    "cat /opt/clickbuild/backend/app/api/v1/endpoints/auth.py",
    "ls /opt/clickbuild/frontend/src/app/ar/",
    "ls /opt/clickbuild/frontend/src/app/ 2>/dev/null",
    "ls /opt/clickbuild/frontend/src/app/'[locale]'/ 2>/dev/null || ls /opt/clickbuild/frontend/src/app/\\[locale\\]/ 2>/dev/null",
    "find /opt/clickbuild/frontend/src -name '*.tsx' | grep -v node_modules",
]

for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))
    err = stderr.read().decode('utf-8', errors='replace')
    if err.strip():
        print("ERR:", err[:100])

client.close()
