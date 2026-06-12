#!/usr/bin/env python
"""Setup Nginx config for odooclickbuild.com"""
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
# HTTP redirect + acme challenge
server {
    listen 80;
    server_name odooclickbuild.com www.odooclickbuild.com;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}

server {
    listen 80;
    server_name ~^.+\\.odooclickbuild\\.com$;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / { return 301 https://$host$request_uri; }
}

# Temporary HTTP preview on port 8080 (before SSL)
server {
    listen 8080;
    server_name _;

    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

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
    "ln -sf /etc/nginx/sites-available/odooclickbuild /etc/nginx/sites-enabled/odooclickbuild",
    "rm -f /etc/nginx/sites-enabled/default",
    "ufw allow 8080/tcp 2>/dev/null || true",
    "nginx -t",
    "nginx -s reload",
    "echo NGINX_OK",
]
stdin, stdout, stderr = client.exec_command(" && ".join(cmds), timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err.strip():
    print("STDERR:", err[:200])

# Test
stdin, stdout, stderr = client.exec_command("curl -s http://127.0.0.1:8080/ | head -5")
print("Site preview:", stdout.read().decode('utf-8', errors='replace')[:300])

client.close()
print("\nDone!")
