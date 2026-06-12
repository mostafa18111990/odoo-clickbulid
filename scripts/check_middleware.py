#!/usr/bin/env python
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    "cat /opt/clickbuild/frontend/src/middleware.ts 2>/dev/null || echo NOT_FOUND",
    "cat /opt/clickbuild/frontend/src/i18n/request.ts 2>/dev/null || echo NOT_FOUND",
    "ls /opt/clickbuild/frontend/src/",
    "ls /opt/clickbuild/frontend/src/i18n/ 2>/dev/null || echo NO_I18N_DIR",
    "cat /opt/clickbuild/frontend/next.config.js",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode('utf-8', errors='replace'))
client.close()
