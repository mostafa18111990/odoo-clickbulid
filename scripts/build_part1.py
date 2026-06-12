#!/usr/bin/env python3
"""Part 1 - docker-compose.yml, odoo.conf, nginx.conf"""
import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('129.121.98.243', username='root', password='Mh@01007121878')

def upload(path, content):
    sftp = ssh.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f'  ✅ {path}')

# ─────────────────────────────────────────────────────
# docker-compose.yml
# ─────────────────────────────────────────────────────
DOCKER_COMPOSE = '''version: "3.9"

services:

  postgres:
    image: postgres:15-alpine
    container_name: odoo_saas_postgres
    restart: always
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo_pg_pass_2024
      POSTGRES_DB: postgres
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5433:5432"
    networks:
      - odoo_net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U odoo"]
      interval: 10s
      timeout: 5s
      retries: 5

  odoo:
    image: odoo:17
    container_name: odoo_saas_app
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8069:8069"
      - "127.0.0.1:8072:8072"
    volumes:
      - ./addons:/mnt/extra-addons
      - ./filestore:/var/lib/odoo
      - ./config/odoo.conf:/etc/odoo/odoo.conf
      - ./logs:/var/log/odoo
    environment:
      - HOST=postgres
      - PORT=5432
      - USER=odoo
      - PASSWORD=odoo_pg_pass_2024
    networks:
      - odoo_net
    command: ["odoo", "--config=/etc/odoo/odoo.conf"]

  nginx:
    image: nginx:alpine
    container_name: odoo_saas_nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certbot/www:/var/www/certbot:ro
      - ./certbot/conf:/etc/letsencrypt:ro
    depends_on:
      - odoo
    networks:
      - odoo_net

  certbot:
    image: certbot/certbot
    container_name: odoo_saas_certbot
    volumes:
      - ./certbot/www:/var/www/certbot
      - ./certbot/conf:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

volumes:
  postgres_data:

networks:
  odoo_net:
    driver: bridge
'''

# ─────────────────────────────────────────────────────
# odoo.conf
# ─────────────────────────────────────────────────────
ODOO_CONF = '''\
[options]
; ── Database ──
db_host = postgres
db_port = 5432
db_user = odoo
db_password = odoo_pg_pass_2024
db_name = False

; ── dbfilter: map subdomain to database ──
; Use ^%d$ when subdomain matches DB name exactly
; Use ^%h$ when full hostname matches DB name
dbfilter = ^%d$

; ── Master admin password ──
admin_passwd = SaaS_Master_2024!

; ── Proxy ──
proxy_mode = True

; ── Addons ──
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons

; ── Workers (production) ──
workers = 4
max_cron_threads = 2

; ── Memory limits ──
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 600
limit_time_real = 1200

; ── Logging ──
logfile = /var/log/odoo/odoo.log
log_level = info
log_handler = :INFO

; ── Filestore ──
data_dir = /var/lib/odoo

; ── HTTP ──
xmlrpc_port = 8069
longpolling_port = 8072

; ── Security ──
list_db = False
'''

# ─────────────────────────────────────────────────────
# nginx.conf
# ─────────────────────────────────────────────────────
NGINX_CONF = '''
# ─── Rate limiting ───
limit_req_zone $binary_remote_addr zone=odoo:10m rate=10r/s;

upstream odoo_backend {
    server odoo:8069;
    keepalive 32;
}

upstream odoo_longpolling {
    server odoo:8072;
    keepalive 8;
}

# ─── HTTP → HTTPS redirect ───
server {
    listen 80;
    server_name _;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# ─── HTTPS wildcard — all subdomains ───
server {
    listen 443 ssl http2;
    server_name ~^(?P<tenant>.+)\\.myerp\\.com$;

    ssl_certificate     /etc/letsencrypt/live/myerp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myerp.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 200m;
    proxy_read_timeout   720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout   720s;

    # Gzip
    gzip on;
    gzip_types text/css text/plain application/javascript application/json image/svg+xml;
    gzip_min_length 1000;

    # ── Longpolling / WebSocket ──
    location /websocket {
        proxy_pass http://odoo_longpolling;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /longpolling {
        proxy_pass http://odoo_longpolling;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # ── Static files — cache aggressively ──
    location ~* /web/static/ {
        proxy_pass http://odoo_backend;
        proxy_set_header Host $host;
        proxy_buffering on;
        proxy_cache_valid 200 60m;
        expires 864000;
        add_header Cache-Control "public, immutable";
    }

    # ── Main Odoo proxy ──
    location / {
        limit_req zone=odoo burst=20 nodelay;

        proxy_pass http://odoo_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;

        # Required for Odoo proxy_mode
        proxy_redirect off;
        proxy_buffering off;

        # Cookie fix
        proxy_cookie_path / "/; SameSite=Lax; Secure";
    }
}

# ─── Admin panel ───
server {
    listen 443 ssl http2;
    server_name admin.myerp.com;

    ssl_certificate     /etc/letsencrypt/live/myerp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/myerp.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options SAMEORIGIN always;

    client_max_body_size 200m;
    proxy_read_timeout 720s;

    location /websocket {
        proxy_pass http://odoo_longpolling;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }

    location /longpolling {
        proxy_pass http://odoo_longpolling;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://odoo_backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
        proxy_buffering off;
    }
}
'''

print('── Uploading infrastructure files ──')
upload('/opt/odoo-saas/docker-compose.yml', DOCKER_COMPOSE)
upload('/opt/odoo-saas/config/odoo.conf', ODOO_CONF)
upload('/opt/odoo-saas/config/nginx.conf', NGINX_CONF)
print('\n✅ Part 1 done!')
ssh.close()
