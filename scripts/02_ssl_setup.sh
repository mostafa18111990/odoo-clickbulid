#!/bin/bash
# ClickBuild SSL Wildcard Setup
# يجب تشغيله بعد إعداد DNS:
#   A record:    clickbuild.com       → IP السيرفر
#   A record:    *.clickbuild.com     → IP السيرفر
# Run as root: bash 02_ssl_setup.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

DOMAIN="clickbuild.com"
ADMIN_EMAIL="admin@clickbuild.com"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║         ClickBuild SSL Setup                 ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ─── Nginx Config الرئيسي ─────────────────────────────────────────────────────
info "إعداد Nginx الرئيسي..."

cat > /etc/nginx/nginx.conf << 'NGINX_CONF'
user www-data;
worker_processes auto;
pid /run/nginx.pid;
include /etc/nginx/modules-enabled/*.conf;

events {
    worker_connections 2048;
    multi_accept on;
    use epoll;
}

http {
    # Basic
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    server_tokens off;
    client_max_body_size 100M;

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    access_log /var/log/nginx/access.log main;
    error_log  /var/log/nginx/error.log;

    # Gzip
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript
               text/xml application/xml application/xml+rss text/javascript;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;

    # الـ Sites
    include /etc/nginx/sites-enabled/*;
}
NGINX_CONF

# ─── Landing Page Config ──────────────────────────────────────────────────────
cat > /etc/nginx/sites-available/clickbuild-main << SITE_CONF
# ─── clickbuild.com (Landing Page) ───────────────────────────────────────────
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN} www.${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options SAMEORIGIN always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Frontend (Next.js)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }

    # Backend API
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Auth endpoints - rate limit أشد
    location /api/auth/login {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
SITE_CONF

# ─── Wildcard Odoo Instances Config ──────────────────────────────────────────
cat > /etc/nginx/sites-available/clickbuild-instances << 'WILD_CONF'
# ─── *.clickbuild.com (Odoo Instances) ───────────────────────────────────────
# هذا الملف يتحكم في كل الـ subdomains تلقائياً
# كل instance لها ملف منفصل في /etc/nginx/sites-available/instances/

server {
    listen 80;
    server_name ~^(?<subdomain>.+)\.clickbuild\.com$;
    return 301 https://$host$request_uri;
}
WILD_CONF

# ─── Template لكل Odoo Instance ──────────────────────────────────────────────
mkdir -p /etc/nginx/sites-available/instances
cat > /opt/clickbuild/nginx/instance.template << 'TEMPLATE'
# Instance: {{SUBDOMAIN}}.clickbuild.com
# Created: {{CREATED_AT}}
# Odoo Version: {{ODOO_VERSION}}

server {
    listen 443 ssl http2;
    server_name {{SUBDOMAIN}}.clickbuild.com;

    ssl_certificate     /etc/letsencrypt/live/clickbuild.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/clickbuild.com/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options SAMEORIGIN always;

    # Odoo Web
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

    # Odoo Longpolling (notifications)
    location /longpolling {
        proxy_pass http://127.0.0.1:{{LONGPOLLING_PORT}};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Static files caching
    location ~* /web/static/ {
        proxy_pass http://127.0.0.1:{{ODOO_PORT}};
        proxy_cache_valid 200 60d;
        add_header Cache-Control "public, immutable";
    }

    # Gzip
    gzip on;
    gzip_types text/css application/javascript application/json;
}
TEMPLATE

ln -sf /etc/nginx/sites-available/clickbuild-main /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/clickbuild-instances /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

nginx -t
log "تم إعداد Nginx"

# ─── SSL Certificate (Wildcard) ───────────────────────────────────────────────
info "طلب SSL Wildcard Certificate..."
echo ""
warn "مهم: تأكد من إعداد DNS قبل المتابعة:"
echo "  A record: ${DOMAIN}   → $(curl -s ifconfig.me)"
echo "  A record: *.${DOMAIN} → $(curl -s ifconfig.me)"
echo ""
read -p "هل تم إعداد DNS؟ (y/n): " DNS_READY

if [ "$DNS_READY" = "y" ]; then
    # الطريقة: DNS Challenge لأن Wildcard يحتاجه
    certbot certonly \
        --manual \
        --preferred-challenges dns \
        -d "${DOMAIN}" \
        -d "*.${DOMAIN}" \
        --agree-tos \
        --email "${ADMIN_EMAIL}" \
        --no-eff-email

    log "تم الحصول على SSL Certificate"

    # Auto-renewal
    cat > /etc/cron.d/certbot-renewal << 'CRON'
0 12 * * * root certbot renew --quiet --post-hook "systemctl reload nginx"
CRON
    log "تم إعداد Auto-renewal"

    systemctl reload nginx
    log "تم تطبيق إعدادات Nginx"
else
    warn "سيتم تخطي SSL الآن - شغّل هذا السكريبت مرة أخرى بعد إعداد DNS"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║           ✅ تم إعداد SSL!                   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "الخطوة التالية:"
echo "  bash 03_build_odoo_image.sh"
echo ""
