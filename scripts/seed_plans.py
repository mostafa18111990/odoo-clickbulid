#!/usr/bin/env python
"""Check Plan model and seed plans"""
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
    "cat /opt/clickbuild/backend/app/models/subscription.py",
    "cd /opt/clickbuild/backend && source venv/bin/activate && python -c \"from app.models.subscription import Plan; import inspect; print([c.key for c in Plan.__table__.columns])\" 2>&1",
]

for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    stdin, stdout, stderr = client.exec_command(f"bash -c '{cmd}'", timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))
    err = stderr.read().decode('utf-8', errors='replace')
    if err.strip():
        print("ERR:", err[:200])

client.close()
