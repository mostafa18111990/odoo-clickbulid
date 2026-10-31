#!/usr/bin/env bash
# Protected boundary for credential-rotation rehearsal and production execution.
set -Eeuo pipefail
umask 077

expected_caller=github-runner
workspace=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid
mode=${1:-}
expected_sha=${2:-}
run_id=${3:-}
state_root=/var/lib/clickbuild-credential-rotation

[[ "${SUDO_USER:-}" == "$expected_caller" ]] || exit 10
[[ "$mode" == rehearse || "$mode" == production ]] || exit 11
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]] || exit 12
[[ "$run_id" =~ ^[0-9]{1,20}$ ]] || exit 13
[[ "$(git -C "$workspace" rev-parse HEAD)" == "$expected_sha" ]] || exit 14

run_root="/run/clickbuild-credential-rotation-$run_id"
[[ "$run_root" == /run/clickbuild-credential-rotation-* ]] || exit 15
install -d -o root -g root -m 700 "$run_root" "$state_root"
cleanup() { rm -rf -- "$run_root"; }
trap cleanup EXIT

for source_name in rotate_odoo_runtime_credentials.sh saas_backup_all.sh; do
    source_path="$workspace/scripts/$source_name"
    [[ -f "$source_path" ]] || exit 16
    install -o root -g root -m 600 "$source_path" "$run_root/$source_name"
    bash -n "$run_root/$source_name"
done

marker="$state_root/rehearsed-$expected_sha"
if [[ "$mode" == rehearse ]]; then
    bash "$run_root/rotate_odoo_runtime_credentials.sh" rehearse "$run_id"
    printf 'sha=%s\nrehearsed_at=%s\n' "$expected_sha" "$(date -u +%FT%TZ)" >"$marker"
    chmod 600 "$marker"
    echo "CREDENTIAL_ROTATION_REHEARSAL_RECORDED sha=$expected_sha"
else
    [[ -s "$marker" ]] || {
        echo 'FAIL: the same release SHA has not passed rehearsal' >&2
        exit 17
    }
    SAAS_BACKUP_SCRIPT="$run_root/saas_backup_all.sh" \
        bash "$run_root/rotate_odoo_runtime_credentials.sh" production "$run_id"
fi
