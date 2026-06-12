#!/usr/bin/env python3
"""Setup odoo.clickbulid.com domain with SSL"""
import paramiko, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('129.121.98.243', username='root', password='Mh@01007121878')

def run(cmd, timeout=120):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    return (o.read().decode('utf-8','replace') + e.read().decode('utf-8','replace')).strip()

def upload(path, content):
    sftp = ssh.open_sftp()
    with sftp.open(path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f'  ✅ {path}')

# ─────────────────────────────────────────────────────
# 1. nginx.conf
# ─────────────────────────────────────────────────────
NGINX = r"""user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    sendfile on;
    keepalive_timeout 65;
    gzip on;
    gzip_types text/css text/plain application/javascript application/json;
    limit_req_zone $binary_remote_addr zone=odoo:10m rate=20r/s;

    upstream odoo_backend    { server odoo:8069; keepalive 32; }
    upstream odoo_longpolling { server odoo:8072; keepalive 8; }

    # HTTP: certbot + redirect to HTTPS
    server {
        listen 80;
        server_name odoo.clickbulid.com *.clickbulid.com;
        location /.well-known/acme-challenge/ { root /var/www/certbot; }
        location / { return 301 https://$host$request_uri; }
    }

    # HTTP: direct IP fallback (no redirect)
    server {
        listen 80 default_server;
        server_name _;
        location /.well-known/acme-challenge/ { root /var/www/certbot; }
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
        }
        location / {
            proxy_pass http://odoo_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_redirect off; proxy_buffering off;
            client_max_body_size 200m;
        }
    }

    # HTTPS: odoo.clickbulid.com — main / admin
    server {
        listen 443 ssl http2;
        server_name odoo.clickbulid.com;
        ssl_certificate     /etc/letsencrypt/live/odoo.clickbulid.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/odoo.clickbulid.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        ssl_session_cache shared:SSL:10m;
        add_header Strict-Transport-Security "max-age=31536000" always;
        add_header X-Frame-Options SAMEORIGIN always;
        add_header X-Content-Type-Options nosniff always;
        client_max_body_size 200m;
        proxy_read_timeout 720s; proxy_connect_timeout 720s; proxy_send_timeout 720s;
        location /websocket {
            proxy_pass http://odoo_longpolling;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
        }
        location /longpolling {
            proxy_pass http://odoo_longpolling;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
        }
        location ~* /web/static/ {
            proxy_pass http://odoo_backend;
            proxy_set_header Host $host;
            expires 7d;
            add_header Cache-Control "public, immutable";
        }
        location / {
            limit_req zone=odoo burst=30 nodelay;
            proxy_pass http://odoo_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_redirect off; proxy_buffering off;
        }
    }

    # HTTPS: *.clickbulid.com — tenant subdomains
    server {
        listen 443 ssl http2;
        server_name ~^(?P<sub>[^.]+)\.clickbulid\.com$;
        ssl_certificate     /etc/letsencrypt/live/odoo.clickbulid.com/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/odoo.clickbulid.com/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;
        add_header X-Frame-Options SAMEORIGIN always;
        client_max_body_size 200m;
        proxy_read_timeout 720s;
        location /websocket {
            proxy_pass http://odoo_longpolling;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "Upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
        }
        location /longpolling {
            proxy_pass http://odoo_longpolling;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto https;
        }
        location / {
            limit_req zone=odoo burst=30 nodelay;
            proxy_pass http://odoo_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
            proxy_redirect off; proxy_buffering off;
        }
    }
}
"""

# ─────────────────────────────────────────────────────
# 2. docker-compose.yml
# ─────────────────────────────────────────────────────
COMPOSE = """services:

  postgres:
    image: postgres:15-alpine
    container_name: odoo_saas_postgres
    restart: always
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo_pg_pass_2024
      POSTGRES_DB: postgres
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
    image: odoo:19
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
      - odoo_data:/var/lib/odoo
      - ./config/odoo.conf:/etc/odoo/odoo.conf
    environment:
      - HOST=postgres
      - PORT=5432
      - USER=odoo
      - PASSWORD=odoo_pg_pass_2024
    networks:
      - odoo_net

  nginx:
    image: nginx:alpine
    container_name: odoo_saas_nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./certbot/www:/var/www/certbot:ro
    depends_on:
      - odoo
    networks:
      - odoo_net

  certbot:
    image: certbot/certbot
    container_name: odoo_saas_certbot
    restart: always
    volumes:
      - ./certbot/www:/var/www/certbot
      - /etc/letsencrypt:/etc/letsencrypt
    entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"

volumes:
  postgres_data:
  odoo_data:

networks:
  odoo_net:
    driver: bridge
"""

# ─────────────────────────────────────────────────────
# 3. odoo.conf
# ─────────────────────────────────────────────────────
ODOO_CONF = """[options]
db_host = postgres
db_port = 5432
db_user = odoo
db_password = odoo_pg_pass_2024
db_name = False

; subdomain -> DB name: odoo.clickbulid.com -> DB: odoo
;                       client1.clickbulid.com -> DB: client1
dbfilter = ^%d$

admin_passwd = SaaS_Master_2024!
proxy_mode = True
list_db = True

addons_path = /usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons

workers = 4
max_cron_threads = 2
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
limit_request = 8192
limit_time_cpu = 600
limit_time_real = 1200

log_level = info
data_dir = /var/lib/odoo
xmlrpc_port = 8069
longpolling_port = 8072
"""

# ── Upload all ──
print('── Uploading configs ──')
upload('/opt/odoo-saas/config/nginx.conf', NGINX)
upload('/opt/odoo-saas/docker-compose.yml', COMPOSE)
upload('/opt/odoo-saas/config/odoo.conf', ODOO_CONF)

# ── Stop nginx to free port 80 for certbot ──
print('\n── Getting SSL certificate ──')
print(run('docker stop odoo_saas_nginx 2>&1'))
time.sleep(3)

# Check if cert exists
cert_check = run('ls /etc/letsencrypt/live/odoo.clickbulid.com/fullchain.pem 2>/dev/null || echo MISSING')
if 'MISSING' in cert_check:
    result = run(
        'certbot certonly --standalone --non-interactive --agree-tos '
        '-m admin@clickbulid.com -d odoo.clickbulid.com 2>&1',
        timeout=120
    )
    print(result)
else:
    print('  ✅ SSL cert already exists')

cert_files = run('ls /etc/letsencrypt/live/odoo.clickbulid.com/ 2>/dev/null || echo MISSING')
print(f'  Cert: {cert_files}')

# ── Restart all containers ──
print('\n── Restarting containers ──')
print(run('cd /opt/odoo-saas && docker compose up -d 2>&1'))
time.sleep(20)

print('\n=== Status ===')
print(run('docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"'))

# ── Test ──
print('\n── Testing ──')
r1 = run('curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/ --connect-timeout 5')
r2 = run('curl -s -o /dev/null -w "%{http_code}" -k https://odoo.clickbulid.com/ --connect-timeout 10 2>/dev/null')
print(f'  http://129.121.98.243       → {r1}')
print(f'  https://odoo.clickbulid.com → {r2}')

print('\n✅ Done! Open: https://odoo.clickbulid.com')
ssh.close()
