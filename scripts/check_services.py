#!/usr/bin/env python
"""Check all services status"""
import paramiko
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    "pm2 list",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/api/v1/health",
    "curl -s http://127.0.0.1:8000/api/v1/health",
    "systemctl is-active clickbuild-api",
    "nginx -t 2>&1 | head -5",
    "cat /etc/nginx/sites-available/odooclickbuild",
    "curl -v http://127.0.0.1/ 2>&1 | head -20",
    "pm2 logs clickbuild-frontend --lines 10 --nostream 2>&1 | tail -15",
]

for cmd in cmds:
    print(f"\n=== {cmd[:70]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(out or err or "(empty)")

client.close()
