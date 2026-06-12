#!/usr/bin/env python
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    # Server resources
    "free -h && echo '---' && df -h / && echo '---' && nproc",
    # Docker status
    "docker ps -a 2>&1 | head -10",
    "docker images | grep odoo",
    # Current provisioning service on server
    "cat /opt/clickbuild/backend/app/services/provisioning.py | head -80",
    # What instance model looks like on server
    "cat /opt/clickbuild/backend/app/models/instance.py",
    # Check if wildcard DNS works
    "curl -sk -o /dev/null -w '%{http_code}' https://test.odoo.clickbulid.com/ 2>&1",
    # Existing nginx sites
    "ls /etc/nginx/sites-enabled/ && ls /etc/nginx/conf.d/ 2>/dev/null",
]
for cmd in cmds:
    print(f"\n{'='*60}")
    print(f"$ {cmd[:70]}")
    print('='*60)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(stdout.read().decode('utf-8', errors='replace'))
    err = stderr.read().decode('utf-8', errors='replace')
    if err.strip(): print("STDERR:", err[:100])

client.close()
