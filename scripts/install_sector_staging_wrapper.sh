#!/bin/bash
# Install the least-privilege sudo boundary for the protected staging workflow.
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || {
    echo 'Run as root.' >&2
    exit 1
}

WRAPPER=/usr/local/sbin/clickbuild-sector-staging-wrapper
SUDOERS=/etc/sudoers.d/clickbuild-sector-staging
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid

cat > "$WRAPPER" <<'WRAPPER_SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

EXPECTED_CALLER=github-runner
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid
SCRIPT="$WORKSPACE/scripts/smoke_odoo20_sector_bundles.sh"
EXPECTED_SHA=${1:-}
RUN_ID=${2:-}

[ "${SUDO_USER:-}" = "$EXPECTED_CALLER" ] || {
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
[ -f "$SCRIPT" ] || {
    echo 'FAIL: staging smoke script missing' >&2
    exit 13
}
ACTUAL_SHA=$(git -C "$WORKSPACE" rev-parse HEAD)
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || {
    echo "FAIL: checkout SHA mismatch ($ACTUAL_SHA != $EXPECTED_SHA)" >&2
    exit 14
}

ROOT_SCRIPT="/run/clickbuild-sector-staging-${RUN_ID}.sh"
cleanup() { rm -f "$ROOT_SCRIPT"; }
trap cleanup EXIT
install -o root -g root -m 700 "$SCRIPT" "$ROOT_SCRIPT"
/bin/bash "$ROOT_SCRIPT" "$RUN_ID"
WRAPPER_SCRIPT
chown root:root "$WRAPPER"
chmod 755 "$WRAPPER"

printf '%s\n' \
    'github-runner ALL=(root) NOPASSWD: /usr/local/sbin/clickbuild-sector-staging-wrapper *' \
    > "$SUDOERS"
chown root:root "$SUDOERS"
chmod 440 "$SUDOERS"
visudo -cf "$SUDOERS"

test -f "$WORKSPACE/scripts/smoke_odoo20_sector_bundles.sh" || {
    echo "WARN: $WORKSPACE has not checked out the staging smoke script yet." >&2
}
echo "Installed $WRAPPER with a single-command sudo rule for github-runner."
