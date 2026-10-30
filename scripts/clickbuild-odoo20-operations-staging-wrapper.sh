#!/usr/bin/env bash
# Least-privilege root boundary for the protected operations staging check.
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
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || {
    echo 'FAIL: invalid release SHA' >&2
    exit 11
}
[[ "$RUN_ID" =~ ^[0-9]{1,20}$ ]] || {
    echo 'FAIL: invalid run id' >&2
    exit 12
}

ACTUAL_SHA=$(git -C "$WORKSPACE" rev-parse HEAD)
[[ "$ACTUAL_SHA" == "$EXPECTED_SHA" ]] || {
    echo 'FAIL: checkout SHA mismatch' >&2
    exit 13
}

ROOT_DIR="/run/clickbuild-odoo20-operations-$RUN_ID"
[[ "$ROOT_DIR" == /run/clickbuild-odoo20-operations-* ]] || exit 14
cleanup() { rm -rf -- "$ROOT_DIR"; }
trap cleanup EXIT
install -d -o root -g root -m 700 "$ROOT_DIR"
for script in saas-sync-tenant-metrics.sh saas_backup_all.sh; do
    source_path="$WORKSPACE/scripts/$script"
    [[ -f "$source_path" ]] || {
        echo "FAIL: missing $script" >&2
        exit 15
    }
    install -o root -g root -m 700 "$source_path" "$ROOT_DIR/$script"
    bash -n "$ROOT_DIR/$script"
done

DRY_RUN=1 bash "$ROOT_DIR/saas-sync-tenant-metrics.sh"
SAAS_BACKUP_VALIDATE_ONLY=1 \
SAAS_BACKUP_LOG="/tmp/clickbuild-staging-backup-validation-$RUN_ID.log" \
    bash "$ROOT_DIR/saas_backup_all.sh"
echo 'STAGING_OPERATIONS_OK'
