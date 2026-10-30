#!/usr/bin/env bash
# Protected production deployment for Odoo 19/20 metrics and verified backups.
set -Eeuo pipefail
umask 077

EXPECTED_CALLER=github-runner
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid
EXPECTED_SHA=${1:-}
RUN_ID=${2:-}

[[ "${SUDO_USER:-}" == "$EXPECTED_CALLER" ]] || {
    echo 'FAIL: wrapper may only be called by github-runner' >&2
    exit 10
}
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || exit 11
[[ "$RUN_ID" =~ ^[0-9]{1,20}$ ]] || exit 12
[[ "$(git -C "$WORKSPACE" rev-parse HEAD)" == "$EXPECTED_SHA" ]] || exit 13

RUN_ROOT="/run/clickbuild-odoo20-operations-production-$RUN_ID"
[[ "$RUN_ROOT" == /run/clickbuild-odoo20-operations-production-* ]] || exit 14
install -d -o root -g root -m 700 "$RUN_ROOT"
cleanup_run_root() { rm -rf -- "$RUN_ROOT"; }
trap cleanup_run_root EXIT

for source_name in \
    saas_backup_all.sh \
    saas-sync-tenant-metrics.sh \
    saas-metrics-sync.service \
    saas-metrics-sync.timer; do
    source_path="$WORKSPACE/scripts/$source_name"
    [[ -f "$source_path" ]] || {
        echo "FAIL: missing $source_name" >&2
        exit 15
    }
    install -o root -g root -m 600 "$source_path" "$RUN_ROOT/$source_name"
done
bash -n "$RUN_ROOT/saas_backup_all.sh"
bash -n "$RUN_ROOT/saas-sync-tenant-metrics.sh"

STAMP=$(date -u +%Y%m%d_%H%M%S)
SNAPSHOT_ROOT="/opt/backups/pre-odoo20-operations-$STAMP"
[[ "$SNAPSHOT_ROOT" == /opt/backups/pre-odoo20-operations-* ]] || exit 16
install -d -o root -g root -m 700 "$SNAPSHOT_ROOT"

# The snapshot is taken with the new reader before any installed file changes.
# It contains both PostgreSQL planes, all four filestore volumes, deployed code,
# runtime configuration, and verified checksums.
BACKUP_ROOT="$SNAPSHOT_ROOT" \
SAAS_BACKUP_LOG="$SNAPSHOT_ROOT/backup.log" \
SAAS_BACKUP_SKIP_OFFSITE=1 \
    bash "$RUN_ROOT/saas_backup_all.sh"
SNAPSHOT_DAY="$SNAPSHOT_ROOT/$(date +%Y-%m-%d)"
test -s "$SNAPSHOT_DAY/MANIFEST.txt"
(
    cd "$SNAPSHOT_DAY"
    sha256sum -c SHA256SUMS >/dev/null
)
odoo20_count=$(sed -n 's/^odoo20_database_count=//p' "$SNAPSHOT_DAY/MANIFEST.txt")
[[ "$odoo20_count" =~ ^[1-9][0-9]*$ ]] || {
    echo 'FAIL: verified snapshot contains no Odoo 20 database' >&2
    exit 17
}

STATE_DIR="$SNAPSHOT_ROOT/installed-before"
install -d -o root -g root -m 700 "$STATE_DIR"
targets=(
    /usr/local/bin/saas-backup-all.sh
    /usr/local/bin/saas-sync-tenant-metrics.sh
    /etc/systemd/system/saas-metrics-sync.service
    /etc/systemd/system/saas-metrics-sync.timer
)
for target in "${targets[@]}"; do
    name=$(printf '%s' "$target" | sed 's#^/##; s#/#__#g')
    if [[ -e "$target" ]]; then
        cp -a -- "$target" "$STATE_DIR/$name"
    else
        : >"$STATE_DIR/$name.absent"
    fi
done

deployment_started=0
rollback() {
    status=$?
    trap - ERR
    set +e
    if [[ "$deployment_started" == "1" ]]; then
        echo "ROLLBACK: restoring installed operations files from $STATE_DIR" >&2
        for target in "${targets[@]}"; do
            name=$(printf '%s' "$target" | sed 's#^/##; s#/#__#g')
            if [[ -f "$STATE_DIR/$name" ]]; then
                cp -a -- "$STATE_DIR/$name" "$target"
            elif [[ -f "$STATE_DIR/$name.absent" ]]; then
                rm -f -- "$target"
            fi
        done
        systemctl daemon-reload
        systemctl restart saas-backup.timer
        systemctl restart saas-metrics-sync.timer
    fi
    echo "ROLLBACK_COMPLETE snapshot=$SNAPSHOT_ROOT" >&2
    exit "$status"
}
trap rollback ERR

deployment_started=1
install -o root -g root -m 755 "$RUN_ROOT/saas_backup_all.sh" /usr/local/bin/saas-backup-all.sh
install -o root -g root -m 755 "$RUN_ROOT/saas-sync-tenant-metrics.sh" /usr/local/bin/saas-sync-tenant-metrics.sh
install -o root -g root -m 644 "$RUN_ROOT/saas-metrics-sync.service" /etc/systemd/system/saas-metrics-sync.service
install -o root -g root -m 644 "$RUN_ROOT/saas-metrics-sync.timer" /etc/systemd/system/saas-metrics-sync.timer
systemctl daemon-reload
systemctl enable --now saas-backup.timer saas-metrics-sync.timer

DRY_RUN=1 /usr/local/bin/saas-sync-tenant-metrics.sh
systemctl start saas-metrics-sync.service
test "$(systemctl show saas-metrics-sync.service -p Result --value)" = success

# Generate the first normal daily backup with Odoo 20 included, then refresh
# backup status in the control plane.
systemctl start saas-backup.service
test "$(systemctl show saas-backup.service -p Result --value)" = success
DAILY_ROOT="/opt/backups/$(date +%Y-%m-%d)"
test -s "$DAILY_ROOT/MANIFEST.txt"
(
    cd "$DAILY_ROOT"
    sha256sum -c SHA256SUMS >/dev/null
)
systemctl start saas-metrics-sync.service
test "$(systemctl show saas-metrics-sync.service -p Result --value)" = success

unhealthy=$(docker exec odoo_saas_postgres psql -U odoo -d odoo -Atc \
    "select count(*) from saas_tenant
      where state in ('trial','pending_payment','active','grace_period','suspended')
        and api_instance_id is not null and api_instance_id not like 'pending:%'
        and (coalesce(metrics_sync_status,'') <> 'ok'
             or coalesce(backup_sync_status,'') not in ('ok','stale'))")
[[ "$unhealthy" == "0" ]] || {
    echo "FAIL: unhealthy active tenant operations records=$unhealthy" >&2
    exit 18
}

test "$(systemctl is-active saas-backup.timer)" = active
test "$(systemctl is-active saas-metrics-sync.timer)" = active
trap - ERR
deployment_started=0
echo "PRODUCTION_OPERATIONS_OK snapshot=$SNAPSHOT_ROOT odoo20_databases=$odoo20_count"
