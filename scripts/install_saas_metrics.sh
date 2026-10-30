#!/usr/bin/env bash
# Install or update the Odoo 19/20 tenant metrics synchronization service.
set -euo pipefail

SOURCE_DIR=${1:-/tmp}
install -m 0755 "$SOURCE_DIR/saas-sync-tenant-metrics.sh" /usr/local/bin/saas-sync-tenant-metrics.sh
install -m 0644 "$SOURCE_DIR/saas-metrics-sync.service" /etc/systemd/system/saas-metrics-sync.service
install -m 0644 "$SOURCE_DIR/saas-metrics-sync.timer" /etc/systemd/system/saas-metrics-sync.timer
systemctl daemon-reload
systemctl enable --now saas-metrics-sync.timer

# A dry run must cover every active local tenant before the installed service
# is allowed to write fresh values into the control database.
DRY_RUN=1 /usr/local/bin/saas-sync-tenant-metrics.sh
systemctl start saas-metrics-sync.service
test "$(systemctl is-active saas-metrics-sync.timer)" = active
