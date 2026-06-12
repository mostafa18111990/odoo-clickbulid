#!/bin/bash
# Installs the automated daily backup as a systemd timer.
# Idempotent — safe to re-run.
set -e

# 1. Install the worker script
install -m 0755 /tmp/saas_backup_all.sh /usr/local/bin/saas-backup-all.sh
echo "[install_backup] installed /usr/local/bin/saas-backup-all.sh"

# 2. systemd service
cat > /etc/systemd/system/saas-backup.service << 'SVC'
[Unit]
Description=ClickBuild SaaS — daily DB backup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/saas-backup-all.sh
# Hard cap so a runaway backup doesn't block the timer indefinitely
TimeoutStartSec=3600
SVC

# 3. systemd timer — daily at 03:30 UTC (off-peak)
cat > /etc/systemd/system/saas-backup.timer << 'TMR'
[Unit]
Description=Run saas-backup daily at 03:30

[Timer]
OnCalendar=*-*-* 03:30:00 UTC
RandomizedDelaySec=30min
Persistent=true
Unit=saas-backup.service

[Install]
WantedBy=timers.target
TMR

mkdir -p /opt/backups
chmod 0750 /opt/backups
touch /var/log/saas-backup.log

systemctl daemon-reload
systemctl enable --now saas-backup.timer
echo "[install_backup] timer enabled, next run:"
systemctl list-timers saas-backup.timer --no-pager | head -3
