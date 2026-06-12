#!/bin/bash
# ClickBuild VPS Setup Script
# Ubuntu 22.04 LTS
# Run as root: bash 01_setup_vps.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✔]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }
err()  { echo -e "${RED}[✘]${NC} $1"; exit 1; }

# ─── Config ───────────────────────────────────────────────────────────────────
DOMAIN="clickbuild.com"
ADMIN_EMAIL="admin@clickbuild.com"
POSTGRES_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)
APP_DIR="/opt/clickbuild"
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     ClickBuild VPS Setup - Ubuntu 22.04      ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ─── 1. System Update ─────────────────────────────────────────────────────────
info "تحديث النظام..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git unzip vim htop \
    ca-certificates gnupg lsb-release \
    software-properties-common apt-transport-https \
    ufw fail2ban certbot python3-certbot-nginx \
    openssl jq
log "تم تحديث النظام"

# ─── 2. Firewall ──────────────────────────────────────────────────────────────
info "إعداد الـ Firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw --force enable
log "تم إعداد الـ Firewall"

# ─── 3. Fail2Ban ──────────────────────────────────────────────────────────────
info "إعداد Fail2Ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port    = 22
EOF
systemctl enable fail2ban
systemctl restart fail2ban
log "تم إعداد Fail2Ban"

# ─── 4. Docker ────────────────────────────────────────────────────────────────
info "تركيب Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | bash
    systemctl enable docker
    systemctl start docker
    log "تم تركيب Docker"
else
    log "Docker موجود بالفعل"
fi

# Docker Compose
if ! command -v docker-compose &> /dev/null; then
    curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    log "تم تركيب Docker Compose"
fi

# ─── 5. PostgreSQL ────────────────────────────────────────────────────────────
info "تركيب PostgreSQL 16..."
if ! command -v psql &> /dev/null; then
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq postgresql-16 postgresql-client-16
    systemctl enable postgresql
    systemctl start postgresql
fi

# إعداد PostgreSQL
sudo -u postgres psql << EOF
ALTER USER postgres WITH PASSWORD '${POSTGRES_PASSWORD}';
CREATE USER clickbuild WITH PASSWORD '${POSTGRES_PASSWORD}' CREATEDB;
CREATE DATABASE clickbuild_platform OWNER clickbuild;
EOF

# السماح بالاتصال من Docker network
PG_HBA="/etc/postgresql/16/main/pg_hba.conf"
echo "host    all             all             172.16.0.0/12           md5" >> $PG_HBA
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/" /etc/postgresql/16/main/postgresql.conf
systemctl restart postgresql
log "تم تركيب وإعداد PostgreSQL"

# ─── 6. Redis ─────────────────────────────────────────────────────────────────
info "تركيب Redis..."
apt-get install -y -qq redis-server
sed -i "s/# requirepass foobared/requirepass ${REDIS_PASSWORD}/" /etc/redis/redis.conf
sed -i "s/bind 127.0.0.1 ::1/bind 0.0.0.0/" /etc/redis/redis.conf
systemctl enable redis-server
systemctl restart redis-server
log "تم تركيب Redis"

# ─── 7. Nginx ─────────────────────────────────────────────────────────────────
info "تركيب Nginx..."
apt-get install -y -qq nginx
systemctl enable nginx
systemctl start nginx
log "تم تركيب Nginx"

# ─── 8. Python 3.12 ───────────────────────────────────────────────────────────
info "تركيب Python 3.12..."
add-apt-repository -y ppa:deadsnakes/ppa > /dev/null 2>&1
apt-get update -qq
apt-get install -y -qq python3.12 python3.12-venv python3.12-dev python3-pip
log "تم تركيب Python 3.12"

# ─── 9. Node.js 20 ────────────────────────────────────────────────────────────
info "تركيب Node.js 20..."
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
apt-get install -y -qq nodejs
npm install -g pm2
log "تم تركيب Node.js 20"

# ─── 10. Project Structure ────────────────────────────────────────────────────
info "إنشاء هيكل المشروع..."
mkdir -p ${APP_DIR}/{backend,frontend,nginx/sites,docker/odoo19,scripts,backups,logs,ssl}

# حفظ كلمات المرور في ملف آمن
cat > ${APP_DIR}/.env.secrets << EOF
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
DOMAIN=${DOMAIN}
ADMIN_EMAIL=${ADMIN_EMAIL}
GENERATED_AT=$(date)
EOF
chmod 600 ${APP_DIR}/.env.secrets

log "تم إنشاء هيكل المشروع في ${APP_DIR}"

# ─── 11. Docker Network ───────────────────────────────────────────────────────
info "إنشاء Docker Networks..."
docker network create clickbuild-net 2>/dev/null || true
docker network create odoo-instances-net 2>/dev/null || true
log "تم إنشاء Docker Networks"

# ─── 12. Swap (للسيرفرات بـ RAM أقل من 4GB) ──────────────────────────────────
if [ $(free -g | awk '/^Mem:/{print $2}') -lt 4 ]; then
    info "إضافة Swap 2GB..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    log "تم إضافة Swap"
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║           ✅ تم الإعداد بنجاح!               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "كلمات المرور محفوظة في: ${APP_DIR}/.env.secrets"
echo ""
echo "الخطوة التالية:"
echo "  bash 02_ssl_setup.sh"
echo ""
