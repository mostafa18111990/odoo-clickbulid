#!/usr/bin/env python
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

DOMAIN = "odoo.clickbuild.com"

cmds = [
    f"nslookup {DOMAIN} 8.8.8.8 2>&1 | head -10",
    f"host {DOMAIN} 2>&1",
    f"curl -s --max-time 5 -o /dev/null -w '%{{http_code}} %{{redirect_url}}' http://{DOMAIN}/ 2>&1",
    # Check all nginx configs on server
    "ls /etc/nginx/sites-enabled/",
    "cat /etc/nginx/sites-enabled/clickbuild.com 2>/dev/null || echo NOT_FOUND",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
