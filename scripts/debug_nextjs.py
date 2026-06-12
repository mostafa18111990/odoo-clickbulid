#!/usr/bin/env python
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

cmds = [
    # Test directly on port 3000
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ar/login",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/ar",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3000/",
    # Check PM2 logs
    "pm2 logs clickbuild-frontend --lines 20 --nostream 2>&1 | tail -20",
    # Check nginx config
    "nginx -T 2>&1 | grep -A 20 'server {'  | head -30",
    # Test via nginx
    "curl -s -v http://127.0.0.1/ar/login 2>&1 | head -30",
    # Check what port next.js is actually running on
    "ss -tlnp | grep -E '3000|8000|80'",
]
for cmd in cmds:
    print(f"\n=== {cmd[:60]} ===")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    print(stdout.read().decode('utf-8', errors='replace'))

client.close()
