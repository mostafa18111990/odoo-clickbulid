#!/usr/bin/env python
"""Check DB module and run create_tables"""
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
    "cat /opt/clickbuild/backend/app/core/database.py",
    "cat /opt/clickbuild/backend/app/models/subscription.py | head -30",
    "cat /opt/clickbuild/backend/app/models/user.py | head -20",
    "cat /opt/clickbuild/backend/app/models/__init__.py",
]

for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
