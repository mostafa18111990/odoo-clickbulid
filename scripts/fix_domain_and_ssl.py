#!/usr/bin/env python
"""Fix domain to odoo.clickbulid.com and get SSL"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"
EMAIL  = "mostafahelmy1995@gmail.com"
IP     = HOST

print(f"Domain: {DOMAIN}")

# ─── 1. Nginx HTTP-only config (for certbot challenge) ────────────────────────
nginx_http = f"""\
server {{
    listen 80 default_server;
    server_name {DOMAIN} *.{DOMAIN} _;

    client_max_body_size 50M;

    location /.well-known/acme-challenge/ {{ root /var/www/html; }}

    location /api/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}

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

# ─── 2. Nginx HTTPS config (after SSL) ────────────────────────────────────────
nginx_ssl = f"""\
# HTTP -> HTTPS redirect
server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

server {{
    listen 80;
    server_name ~^.+\\.{DOMAIN.replace('.', '\\.')}$;
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

# HTTPS - Main Platform
server {{
    listen 443 ssl http2;
    server_name {DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;

    client_max_body_size 50M;

    location /api/ {{
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 60s;
    }}

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

# ─── 3. Instance nginx template ───────────────────────────────────────────────
instance_tpl = f"""\
# {{SUBDOMAIN}}.{DOMAIN}
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

# Write configs
sftp.putfo(io.BytesIO(nginx_http.encode()), '/etc/nginx/sites-available/clickbuild-platform')
sftp.putfo(io.BytesIO(nginx_ssl.encode()),  '/etc/nginx/sites-available/clickbuild-platform-ssl')
client.exec_command("mkdir -p /opt/clickbuild/nginx/templates")
time.sleep(0.2)
sftp.putfo(io.BytesIO(instance_tpl.encode()), '/opt/clickbuild/nginx/templates/instance.template')
print("[OK] Nginx configs written")

# Enable HTTP config and reload
cmds = [
    "rm -f /etc/nginx/sites-enabled/*",
    "ln -sf /etc/nginx/sites-available/clickbuild-platform /etc/nginx/sites-enabled/clickbuild-platform",
    "mkdir -p /var/www/html",
    "nginx -t",
    "nginx -s reload",
    "echo NGINX_OK",
]
stdin, stdout, stderr = client.exec_command(" && ".join(cmds), timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.strip())
if err.strip(): print("STDERR:", err[:200])

# Verify HTTP works on the domain
time.sleep(1)
stdin, stdout, stderr = client.exec_command(f"curl -s --max-time 10 -o /dev/null -w '%{{http_code}}' http://{DOMAIN}/api/health")
code = stdout.read().decode().strip()
print(f"\nHTTP check: http://{DOMAIN}/api/health -> {code}")

if code not in ['200', '301', '302']:
    print("HTTP not accessible yet via domain. Check DNS or wait a bit more.")
    sftp.close(); client.close(); sys.exit(1)

# ─── 4. Get SSL certificate ───────────────────────────────────────────────────
print(f"\nGetting SSL certificate for {DOMAIN}...")
certbot_cmd = (
    f"certbot certonly --nginx "
    f"-d {DOMAIN} "
    f"--non-interactive --agree-tos --email {EMAIL} 2>&1"
)
chan = client.get_transport().open_session()
chan.get_pty()
chan.exec_command(certbot_cmd)
start = time.time()
output = ""
while not chan.exit_status_ready():
    if chan.recv_ready():
        data = chan.recv(4096).decode('utf-8', errors='replace')
        output += data
        print(data, end='', flush=True)
    if time.time() - start > 120:
        print("\n[TIMEOUT]")
        break
    time.sleep(0.2)
remaining = chan.recv(65535).decode('utf-8', errors='replace')
if remaining:
    output += remaining
    print(remaining)
cert_code = chan.recv_exit_status()
print(f"\nCertbot exit code: {cert_code}")

if cert_code != 0:
    print("ERROR: Certificate failed. See output above.")
    sftp.close(); client.close(); sys.exit(1)

# ─── 5. Switch to HTTPS config ────────────────────────────────────────────────
print("\nSwitching to HTTPS...")
cmds2 = [
    "rm -f /etc/nginx/sites-enabled/clickbuild-platform",
    "ln -sf /etc/nginx/sites-available/clickbuild-platform-ssl /etc/nginx/sites-enabled/clickbuild-platform",
    "nginx -t",
    "nginx -s reload",
    "echo HTTPS_OK",
]
stdin, stdout, stderr = client.exec_command(" && ".join(cmds2), timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out.strip())
if err.strip(): print("STDERR:", err[:200])

# ─── 6. Update backend .env ───────────────────────────────────────────────────
stdin, stdout, stderr = client.exec_command("cat /opt/clickbuild/backend/.env")
env_content = stdout.read().decode('utf-8', errors='replace')
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

# ─── 7. Update frontend .env.local ────────────────────────────────────────────
new_env = f"NEXT_PUBLIC_API_URL=https://{DOMAIN}/api/v1\nNEXT_PUBLIC_DOMAIN={DOMAIN}\n"
sftp.putfo(io.BytesIO(new_env.encode()), '/opt/clickbuild/frontend/.env.local')
print("[OK] frontend .env.local updated")

sftp.close()

# Restart backend
stdin, stdout, stderr = client.exec_command("systemctl restart clickbuild-api && sleep 2 && systemctl is-active clickbuild-api")
print(f"[OK] Backend: {stdout.read().decode().strip()}")

# ─── 8. Rebuild frontend with HTTPS URL ───────────────────────────────────────
print("\nRebuilding frontend...")
build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -15"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
b_code = stdout.channel.recv_exit_status()
print(f"Build: {b_code}")

if b_code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | tail -2")
    print(stdout.read().decode())

# ─── 9. Final test ────────────────────────────────────────────────────────────
time.sleep(3)
stdin, stdout, stderr = client.exec_command(f"curl -sk -o /dev/null -w '%{{http_code}}' https://{DOMAIN}/api/health")
code = stdout.read().decode().strip()
print(f"\nFinal HTTPS test: https://{DOMAIN}/api/health -> HTTP {code}")

if code == '200':
    print(f"\nSite is LIVE!")
    print(f"  https://{DOMAIN}")
    print(f"  https://{DOMAIN}/ar/register")
    print(f"  https://{DOMAIN}/ar/login")

# Setup auto-renewal
stdin, stdout, stderr = client.exec_command(
    "(crontab -l 2>/dev/null; echo '0 3 * * * certbot renew --quiet --nginx') | crontab - && echo CRON_OK"
)
print(stdout.read().decode().strip())

client.close()
