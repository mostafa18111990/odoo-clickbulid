#!/usr/bin/env python
"""رفع ملفات المشروع للسيرفر"""
import paramiko
import os
import io
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

BASE_LOCAL  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_REMOTE = "/opt/clickbuild"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

def mkdir_remote(path):
    try:
        sftp.stat(path)
    except FileNotFoundError:
        client.exec_command(f"mkdir -p {path}")
        time.sleep(0.3)

def upload_file(local, remote):
    remote_dir = "/".join(remote.split("/")[:-1])
    mkdir_remote(remote_dir)
    try:
        sftp.put(local, remote)
        print(f"  [OK] {remote}")
    except Exception as e:
        print(f"  [ERR] {remote} -> {e}")

# ─── Docker files ─────────────────────────────────────────────────────────────
docker_files = [
    ("docker/odoo19/Dockerfile",          "docker/odoo19/Dockerfile"),
    ("docker/odoo19/odoo.conf.template",  "docker/odoo19/odoo.conf.template"),
    ("docker/odoo19/entrypoint.sh",       "docker/odoo19/entrypoint.sh"),
]
for local_rel, remote_rel in docker_files:
    local  = os.path.join(BASE_LOCAL, local_rel)
    remote = BASE_REMOTE + "/" + remote_rel
    if os.path.exists(local):
        upload_file(local, remote)

# ─── Backend files ─────────────────────────────────────────────────────────────
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules", ".pytest_cache"}
KEEP_EXTS = {".py", ".txt", ".example", ".ini", ".cfg", ".toml"}

for root, dirs, files in os.walk(os.path.join(BASE_LOCAL, "backend")):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for fname in files:
        ext = os.path.splitext(fname)[1]
        if ext in KEEP_EXTS or fname in {".env.example", "requirements.txt"}:
            local_path  = os.path.join(root, fname)
            rel         = os.path.relpath(local_path, BASE_LOCAL)
            remote_path = BASE_REMOTE + "/" + rel.replace("\\", "/")
            upload_file(local_path, remote_path)

# ─── Nginx template ───────────────────────────────────────────────────────────
# Create the instance template directly on server
nginx_template = r"""# Instance: {{SUBDOMAIN}}.odooclickbuild.com
# Created: {{CREATED_AT}} | Odoo {{ODOO_VERSION}}

server {
    listen 443 ssl http2;
    server_name {{SUBDOMAIN}}.odooclickbuild.com;

    ssl_certificate     /etc/letsencrypt/live/odooclickbuild.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/odooclickbuild.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options SAMEORIGIN always;

    location / {
        proxy_pass http://127.0.0.1:{{ODOO_PORT}};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 720s;
        proxy_connect_timeout 720s;
    }

    location /longpolling {
        proxy_pass http://127.0.0.1:{{LONGPOLLING_PORT}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location ~* /web/static/ {
        proxy_pass http://127.0.0.1:{{ODOO_PORT}};
        add_header Cache-Control "public, immutable";
        proxy_cache_valid 200 60d;
    }

    gzip on;
    gzip_types text/css application/javascript application/json;
}
"""

# كتابة الـ template مباشرة على السيرفر
stdin, stdout, stderr = client.exec_command("cat > /opt/clickbuild/nginx/templates/instance.template << 'TMPL_EOF'\n" + nginx_template + "\nTMPL_EOF")
stdout.read()
print("  [OK] /opt/clickbuild/nginx/templates/instance.template")

sftp.close()
client.close()
print("\nUPLOAD_DONE")
