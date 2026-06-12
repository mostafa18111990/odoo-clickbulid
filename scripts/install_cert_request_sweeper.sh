#!/bin/bash
# Installs the cert-request sweeper pattern:
# 1. Creates /opt/odoo-saas/cert-requests/ (shared with Odoo container)
# 2. Mounts it into the Odoo container via docker-compose patch
# 3. Installs /usr/local/bin/saas-cert-sweeper.sh (host-side worker)
# 4. Installs systemd timer (runs every 2 min)
#
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

# 2. Install sweeper script
cat > "$SWEEPER" << 'SWEEP'
#!/bin/bash
# Sweeps /opt/odoo-saas/cert-requests/*.req and provisions each.
set -e
REQ_DIR=/opt/odoo-saas/cert-requests
LOG=/var/log/saas-cert-sweeper.log

shopt -s nullglob
for req in "$REQ_DIR"/*.req; do
    sub=$(basename "$req" .req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    if [ -z "$sub" ]; then
        rm -f "$req"
        echo "$(date -Is) skipped empty/invalid req" >> "$LOG"
        continue
    fi
    echo "$(date -Is) provisioning $sub.clickbulid.com" >> "$LOG"
    if bash /opt/odoo-saas/provision_tenant_cert.sh "$sub" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.done"
        echo "$(date -Is) DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.error"
        echo "$(date -Is) ERROR $sub (see log above)" >> "$LOG"
    fi
done
SWEEP
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
