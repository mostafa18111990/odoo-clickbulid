#!/usr/bin/env bash
# Least-privilege root boundary for the read-only credential topology audit.
set -Eeuo pipefail
umask 077

expected_caller=github-runner
workspace=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid
expected_sha=${1:-}
run_id=${2:-}

[[ "${SUDO_USER:-}" == "$expected_caller" ]] || {
    echo 'FAIL: wrapper may only be called by github-runner' >&2
    exit 10
}
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]] || exit 11
[[ "$run_id" =~ ^[0-9]{1,20}$ ]] || exit 12
[[ "$(git -C "$workspace" rev-parse HEAD)" == "$expected_sha" ]] || exit 13

source_script="$workspace/scripts/audit_runtime_credential_topology.sh"
[[ -f "$source_script" ]] || exit 14

run_root="/run/clickbuild-credential-audit-$run_id"
[[ "$run_root" == /run/clickbuild-credential-audit-* ]] || exit 15
install -d -o root -g root -m 700 "$run_root"
cleanup() { rm -rf -- "$run_root"; }
trap cleanup EXIT

install -o root -g root -m 600 "$source_script" "$run_root/audit.sh"
bash -n "$run_root/audit.sh"
EXPECTED_EFFECTIVE_USER=root bash "$run_root/audit.sh"
