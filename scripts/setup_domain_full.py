#!/usr/bin/env python
"""
Setup odoo.clickbuild.com:
1. Configure Nginx for HTTP (domain + wildcard subdomains)
2. Update backend .env
3. Update frontend .env.local
4. Rebuild frontend
5. Get SSL certificate (needs DNS to be pointing first)
"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbuild.com"
IP     = HOST

# ─── 1. Nginx config (HTTP only for now, SSL added after cert) ────────────────
nginx_conf = f"""\
# Redirect HTTP to HTTPS (main domain)
server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

# Redirect HTTP to HTTPS (wildcard subdomains)
server {{
    listen 80;
    server_name ~^.+\\.{DOMAIN.replace('.', '\\.')}$;
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

# HTTPS - Main Platform (odoo.clickbuild.com)
server {{
    listen 443 ssl http2;
    server_name {DOMAIN} www.{DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 50M;

    # API
    location /api/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 60s;
    }}

    # Frontend (Next.js)
    location / {{
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }}
}}
"""

# ─── 2. Nginx HTTP-only config (used BEFORE SSL cert is obtained) ─────────────
nginx_http_only = f"""\
# Main platform - HTTP only (temp until SSL)
server {{
    listen 80 default_server;
    server_name {DOMAIN} www.{DOMAIN} _;

    client_max_body_size 50M;

    location /.well-known/acme-challenge/ {{ root /var/www/html; }}

    # API
    location /api/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }}

    # Frontend (Next.js)
    location / {{
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }}
}}
"""

# Write HTTP-only config now (we'll switch to HTTPS after cert)
sftp.putfo(io.BytesIO(nginx_http_only.encode()), '/etc/nginx/sites-available/clickbuild-platform')
# Save full HTTPS config for later
sftp.putfo(io.BytesIO(nginx_conf.encode()), '/etc/nginx/sites-available/clickbuild-platform-ssl')
print("[OK] Nginx configs written")

# ─── 3. Nginx instance template (wildcard subdomains for Odoo) ───────────────
instance_template = f"""\
# Instance: {{{{SUBDOMAIN}}}}.{DOMAIN}
# Created: {{{{CREATED_AT}}}} | Odoo {{{{ODOO_VERSION}}}}

server {{{{
    listen 443 ssl http2;
    server_name {{{{SUBDOMAIN}}}}.{DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options SAMEORIGIN always;

    client_max_body_size 200M;

    location / {{{{
        proxy_pass http://127.0.0.1:{{{{ODOO_PORT}}}};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 720s;
        proxy_connect_timeout 720s;
    }}}}

    location /longpolling {{{{
        proxy_pass http://127.0.0.1:{{{{LONGPOLLING_PORT}}}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }}}}

    location ~* /web/static/ {{{{
        proxy_pass http://127.0.0.1:{{{{ODOO_PORT}}}};
        add_header Cache-Control "public, immutable";
        expires 60d;
    }}}}

    gzip on;
    gzip_types text/css application/javascript application/json;
}}}}

server {{{{
    listen 80;
    server_name {{{{SUBDOMAIN}}}}.{DOMAIN};
    return 301 https://$host$request_uri;
}}}}
"""

client.exec_command("mkdir -p /opt/clickbuild/nginx/templates")
time.sleep(0.3)
sftp.putfo(io.BytesIO(instance_template.encode()), '/opt/clickbuild/nginx/templates/instance.template')
print("[OK] Instance template written")

# ─── 4. Enable new nginx config ───────────────────────────────────────────────
cmds = [
    "rm -f /etc/nginx/sites-enabled/odooclickbuild",
    "rm -f /etc/nginx/sites-enabled/default",
    "ln -sf /etc/nginx/sites-available/clickbuild-platform /etc/nginx/sites-enabled/clickbuild-platform",
    "nginx -t",
    "nginx -s reload",
    "echo NGINX_OK",
]
stdin, stdout, stderr = client.exec_command(" && ".join(cmds), timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err.strip(): print("STDERR:", err[:200])

# ─── 5. Update backend .env ───────────────────────────────────────────────────
stdin, stdout, stderr = client.exec_command("cat /opt/clickbuild/backend/.env")
env_content = stdout.read().decode('utf-8', errors='replace')

# Replace domain references
env_new = ""
for line in env_content.splitlines():
    if line.startswith("DOMAIN="):
        env_new += f"DOMAIN={DOMAIN}\n"
    elif line.startswith("ALLOWED_ORIGINS="):
        env_new += f"ALLOWED_ORIGINS=https://{DOMAIN},http://{IP}\n"
    elif line.startswith("FRONTEND_URL="):
        env_new += f"FRONTEND_URL=https://{DOMAIN}\n"
    else:
        env_new += line + "\n"

sftp.putfo(io.BytesIO(env_new.encode()), '/opt/clickbuild/backend/.env')
print("[OK] backend .env updated")

# ─── 6. Update frontend .env.local ────────────────────────────────────────────
new_env_local = f"""\
NEXT_PUBLIC_API_URL=https://{DOMAIN}/api/v1
NEXT_PUBLIC_DOMAIN={DOMAIN}
NEXT_PUBLIC_INSTANCE_DOMAIN={DOMAIN}
"""
sftp.putfo(io.BytesIO(new_env_local.encode()), '/opt/clickbuild/frontend/.env.local')
print("[OK] frontend .env.local updated")

sftp.close()

# ─── 7. Restart backend ───────────────────────────────────────────────────────
stdin, stdout, stderr = client.exec_command("systemctl restart clickbuild-api && sleep 2 && systemctl is-active clickbuild-api")
print(f"[OK] Backend: {stdout.read().decode().strip()}")

# ─── 8. Rebuild frontend ──────────────────────────────────────────────────────
print("\nRebuilding frontend with domain URL...")
build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -15"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
build_code = stdout.channel.recv_exit_status()
print(f"\nBuild exit code: {build_code}")

if build_code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | tail -2")
    print(stdout.read().decode())
    print("[OK] Frontend restarted")

client.close()
print("\n" + "="*60)
print("NEXT STEPS - Add these DNS records in your domain provider:")
print("="*60)
print(f"\n  Type: A    Name: odoo              Value: {IP}")
print(f"  Type: A    Name: *.odoo            Value: {IP}")
print(f"\n  (في لوحة DNS الخاصة بدومين clickbuild.com)")
print("\nAfter DNS propagates (5-30 min), run: python scripts/get_ssl.py")
