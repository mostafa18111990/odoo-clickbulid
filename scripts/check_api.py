#!/usr/bin/env python
"""Check API routes"""
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
    # Test different health paths
    "curl -s http://127.0.0.1:8000/health",
    "curl -s http://127.0.0.1:8000/api/v1/health",
    "curl -s http://127.0.0.1:8000/",
    # Check FastAPI routes
    "cat /opt/clickbuild/backend/app/main.py",
    "cat /opt/clickbuild/backend/app/api/v1/endpoints/instances.py | head -30",
]

for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
