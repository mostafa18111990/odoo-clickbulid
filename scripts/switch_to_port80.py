#!/usr/bin/env python
"""Switch Nginx to serve on port 80 directly (no SSL, IP-based)"""
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
sftp = client.open_sftp()

nginx_config = """\
server {
    listen 80 default_server;
    server_name _;

    client_max_body_size 50M;

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Frontend (Next.js)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
"""

sftp.putfo(io.BytesIO(nginx_config.encode('utf-8')), '/etc/nginx/sites-available/odooclickbuild')
sftp.close()
print("[OK] Nginx config written")

cmds = [
    "rm -f /etc/nginx/sites-enabled/default",
    "ln -sf /etc/nginx/sites-available/odooclickbuild /etc/nginx/sites-enabled/odooclickbuild",
    "ufw allow 80/tcp 2>/dev/null || true",
    "nginx -t",
    "nginx -s reload",
    "echo NGINX_OK",
]

stdin, stdout, stderr = client.exec_command(" && ".join(cmds), timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err.strip():
    print("STDERR:", err[:400])

# Quick test
import time
time.sleep(1)
stdin, stdout, stderr = client.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1/")
code = stdout.read().decode().strip()
print(f"HTTP status on port 80: {code}")

client.close()
print("Done!")
