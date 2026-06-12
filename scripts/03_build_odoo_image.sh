#!/bin/bash
# بناء وتسجيل Custom Odoo 19 Image
set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✔]${NC} $1"; }
info() { echo -e "${BLUE}[→]${NC} $1"; }

VERSION="19"
IMAGE_NAME="clickbuild/odoo:${VERSION}"

info "بناء ${IMAGE_NAME}..."
cd /opt/clickbuild/docker/odoo19
docker build -t "${IMAGE_NAME}" .
docker tag "${IMAGE_NAME}" "clickbuild/odoo:latest"

log "تم بناء الـ Image: ${IMAGE_NAME}"

# اختبار سريع
info "اختبار الـ Image..."
docker run --rm "${IMAGE_NAME}" odoo --version
log "الـ Image يعمل بشكل صحيح"

echo ""
echo "الخطوة التالية:"
echo "  cd /opt/clickbuild/backend && bash setup_backend.sh"
