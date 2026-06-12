#!/bin/bash
# نشر الـ Backend والـ Frontend على السيرفر
set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✔]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

APP_DIR="/opt/clickbuild"

# ─── Backend ──────────────────────────────────────────────────────────────────
info "نشر Backend..."
cd ${APP_DIR}/backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q

# إنشاء .env من المثال (أول مرة)
[ ! -f .env ] && cp .env.example .env && echo "⚠️  عدّل ملف .env قبل المتابعة!" && exit 1

# Database migrations
alembic upgrade head

# تشغيل FastAPI بـ systemd
cat > /etc/systemd/system/clickbuild-api.service << 'SVC'
[Unit]
Description=ClickBuild FastAPI Backend
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clickbuild/backend
EnvironmentFile=/opt/clickbuild/backend/.env
ExecStart=/opt/clickbuild/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 4
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

# Celery Worker
cat > /etc/systemd/system/clickbuild-worker.service << 'SVC'
[Unit]
Description=ClickBuild Celery Worker
After=redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clickbuild/backend
EnvironmentFile=/opt/clickbuild/backend/.env
ExecStart=/opt/clickbuild/backend/venv/bin/celery -A app.workers.lifecycle worker -l warning
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

# Celery Beat (Scheduler)
cat > /etc/systemd/system/clickbuild-beat.service << 'SVC'
[Unit]
Description=ClickBuild Celery Beat Scheduler
After=redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clickbuild/backend
EnvironmentFile=/opt/clickbuild/backend/.env
ExecStart=/opt/clickbuild/backend/venv/bin/celery -A app.workers.lifecycle beat -l warning
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable clickbuild-api clickbuild-worker clickbuild-beat
systemctl restart clickbuild-api clickbuild-worker clickbuild-beat
log "تم نشر Backend"

# ─── Frontend ─────────────────────────────────────────────────────────────────
info "نشر Frontend..."
cd ${APP_DIR}/frontend
npm install -q
npm run build
pm2 delete clickbuild-frontend 2>/dev/null || true
pm2 start npm --name clickbuild-frontend -- start
pm2 save
log "تم نشر Frontend"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║           ✅ تم النشر بنجاح!                 ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "الموقع: https://clickbuild.com"
echo ""
