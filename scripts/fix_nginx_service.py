#!/usr/bin/env python
"""Fix nginx_service.py - broken f-string nesting"""
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"
CERT   = f"/etc/letsencrypt/live/{DOMAIN}/fullchain.pem"
KEY    = f"/etc/letsencrypt/live/{DOMAIN}/privkey.pem"

# Write nginx_service.py directly - no f-string nesting issues
nginx_service_content = r'''"""Nginx Service - manages per-instance reverse proxy configs"""
import subprocess, os
from pathlib import Path

DOMAIN      = "''' + DOMAIN + r'''"
SITES_DIR   = Path("/etc/nginx/sites-available/instances")
ENABLED_DIR = Path("/etc/nginx/sites-enabled")
CERT_PATH   = "''' + CERT + r'''"
KEY_PATH    = "''' + KEY + r'''"


class NginxService:

    def add_instance_config(self, subdomain: str, port: int,
                            longpolling_port: int, odoo_version: str = "19"):
        """Create nginx config for a new instance and reload nginx"""
        SITES_DIR.mkdir(parents=True, exist_ok=True)
        config_path = SITES_DIR / f"{subdomain}.conf"

        config = (
            f"# Instance: {subdomain} -- Odoo {odoo_version}\n"
            f"server {{\n"
            f"    listen 80;\n"
            f"    server_name {subdomain}.{DOMAIN};\n"
            f"    location /.well-known/acme-challenge/ {{ root /var/www/html; }}\n"
            f"    return 301 https://$host$request_uri;\n"
            f"}}\n\n"
            f"server {{\n"
            f"    listen 443 ssl;\n"
            f"    server_name {subdomain}.{DOMAIN};\n\n"
            f"    ssl_certificate     {CERT_PATH};\n"
            f"    ssl_certificate_key {KEY_PATH};\n"
            f"    ssl_protocols       TLSv1.2 TLSv1.3;\n"
            f"    ssl_ciphers         HIGH:!aNULL:!MD5;\n\n"
            f"    proxy_read_timeout  720s;\n"
            f"    proxy_connect_timeout 720s;\n"
            f"    proxy_send_timeout  720s;\n"
            f"    client_max_body_size 512m;\n\n"
            f"    location / {{\n"
            f"        proxy_pass         http://127.0.0.1:{port};\n"
            f"        proxy_set_header   Host $host;\n"
            f"        proxy_set_header   X-Real-IP $remote_addr;\n"
            f"        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            f"        proxy_set_header   X-Forwarded-Proto $scheme;\n"
            f"        proxy_redirect     off;\n"
            f"    }}\n\n"
            f"    location /longpolling {{\n"
            f"        proxy_pass         http://127.0.0.1:{longpolling_port};\n"
            f"        proxy_set_header   Host $host;\n"
            f"        proxy_set_header   X-Real-IP $remote_addr;\n"
            f"        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            f"        proxy_set_header   X-Forwarded-Proto $scheme;\n"
            f"    }}\n\n"
            f"    location ~* /web/static/ {{\n"
            f"        proxy_pass         http://127.0.0.1:{port};\n"
            f"        expires            864000;\n"
            f"        add_header         Cache-Control \"public, immutable\";\n"
            f"    }}\n\n"
            f"    add_header X-Frame-Options \"SAMEORIGIN\";\n"
            f"    add_header X-Content-Type-Options \"nosniff\";\n"
            f"    gzip on;\n"
            f"}}\n"
        )

        config_path.write_text(config)

        # Enable site
        enabled_link = ENABLED_DIR / f"{subdomain}.conf"
        if not enabled_link.exists():
            enabled_link.symlink_to(config_path)

        # Test + reload nginx
        result = subprocess.run(["nginx", "-t"], capture_output=True)
        if result.returncode == 0:
            subprocess.run(["systemctl", "reload", "nginx"])
        else:
            raise Exception(f"Nginx config error: {result.stderr.decode()}")

    def remove_instance_config(self, subdomain: str):
        enabled_link = ENABLED_DIR / f"{subdomain}.conf"
        config_path  = SITES_DIR / f"{subdomain}.conf"
        if enabled_link.exists():
            enabled_link.unlink()
        if config_path.exists():
            config_path.unlink()
        subprocess.run(["systemctl", "reload", "nginx"])
'''

sftp.putfo(io.BytesIO(nginx_service_content.encode('utf-8')), '/opt/clickbuild/backend/app/services/nginx_service.py')
print("[OK] nginx_service.py fixed")

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# Test import
print("Import test:", run(
    'cd /opt/clickbuild/backend && source venv/bin/activate && '
    'python -c "from app.services.nginx_service import NginxService; print(\'OK\')" 2>&1'
))

# Restart API
print("Restart:", run('systemctl restart clickbuild-api && sleep 4 && curl -s http://127.0.0.1:8000/api/health'))
print("HTTPS:", run("curl -sk -o /dev/null -w '%{http_code}' https://odoo.clickbulid.com/api/health"))

sftp.close()
client.close()
