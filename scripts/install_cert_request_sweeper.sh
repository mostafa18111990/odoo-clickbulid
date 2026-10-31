#!/bin/bash
# Installs the cert-request sweeper pattern:
# 1. Creates /opt/odoo-saas/cert-requests/ (shared with Odoo container)
# 2. Mounts it into the Odoo container via docker-compose patch
# 3. Installs /usr/local/bin/saas-cert-sweeper.sh (host-side worker)
# 4. Installs systemd timer (runs every 2 min)
#
# The sweeper also destroys tenants for <subdomain>.delete.req requests.
# When Odoo writes /opt/odoo-saas/cert-requests/<subdomain>.req, the sweeper:
#   - reads the subdomain
#   - calls /opt/odoo-saas/provision_tenant_cert.sh <subdomain>
#   - on success: writes <subdomain>.done; on fail: writes <subdomain>.error
#   - deletes the .req file
set -e

REQUEST_DIR=/opt/odoo-saas/cert-requests
SWEEPER=/usr/local/bin/saas-cert-sweeper.sh
COMPOSE=/opt/odoo-saas/docker-compose.yml

mkdir -p "$REQUEST_DIR"
chmod 0777 "$REQUEST_DIR"   # Odoo runs as uid 101; sweeper as root

# 1. Mount into Odoo container if not already mounted
if ! grep -q "/mnt/cert-requests" "$COMPOSE"; then
    cp "$COMPOSE" "$COMPOSE.bak.sweeper.$(date +%s)"
    sed -i '/- .\/config\/odoo.conf:\/etc\/odoo\/odoo.conf/a\      - ./cert-requests:/mnt/cert-requests' "$COMPOSE"
    echo "[sweeper] added cert-requests volume to docker-compose.yml"
    cd /opt/odoo-saas && docker compose up -d odoo
else
    echo "[sweeper] volume already mounted in compose"
fi

# 2. Install sweeper + destroyer scripts from this repo (the sweeper hands
#    *.delete.req to the destroyer; without it deletion requests were ignored)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$SWEEPER" ] && cp "$SWEEPER" "$SWEEPER.bak.$(date +%Y%m%d%H%M%S)"
install -m 0755 "$HERE/saas-cert-sweeper.sh" "$SWEEPER"
install -m 0755 "$HERE/saas-tenant-destroyer.sh" /usr/local/bin/saas-tenant-destroyer.sh
chmod +x "$SWEEPER"
echo "[sweeper] installed $SWEEPER"

# 3. Install systemd service + timer
cat > /etc/systemd/system/saas-cert-sweeper.service << 'SVC'
[Unit]
Description=ClickBuild SaaS — tenant cert request sweeper
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/saas-cert-sweeper.sh
SVC

cat > /etc/systemd/system/saas-cert-sweeper.timer << 'TMR'
[Unit]
Description=Run saas-cert-sweeper every 2 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=2min
Unit=saas-cert-sweeper.service

[Install]
WantedBy=timers.target
TMR

systemctl daemon-reload
systemctl enable --now saas-cert-sweeper.timer
echo "[sweeper] systemd timer enabled"
systemctl list-timers saas-cert-sweeper.timer --all | head -3
