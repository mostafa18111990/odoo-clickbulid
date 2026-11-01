#!/bin/bash
# Install a narrow sudo boundary for the protected website staging workflow.
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || {
    echo 'Run as root.' >&2
    exit 1
}

WRAPPER=/usr/local/sbin/clickbuild-website-staging-wrapper
SUDOERS=/etc/sudoers.d/clickbuild-website-staging
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid

cat > "$WRAPPER" <<'WRAPPER_SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

EXPECTED_CALLER=github-runner
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid
EXPECTED_SHA=${1:-}
RUN_ID=${2:-}
SCRIPT="$WORKSPACE/scripts/deploy_saas_website_staging.sh"
ARCHIVE="/tmp/clickbuild-website-staging-${RUN_ID}.tar.gz"

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
    echo 'FAIL: staging deployment script missing' >&2
    exit 13
}
[ -f "$ARCHIVE" ] || {
    echo 'FAIL: staging release archive missing' >&2
    exit 14
}
ACTUAL_SHA=$(git -C "$WORKSPACE" rev-parse HEAD)
[ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || {
    echo "FAIL: checkout SHA mismatch ($ACTUAL_SHA != $EXPECTED_SHA)" >&2
    exit 15
}

ROOT_SCRIPT="/run/clickbuild-website-staging-${RUN_ID}.sh"
ROOT_ARCHIVE="/run/clickbuild-website-staging-${RUN_ID}.tar.gz"
cleanup() { rm -f "$ROOT_SCRIPT" "$ROOT_ARCHIVE"; }
trap cleanup EXIT
install -o root -g root -m 700 "$SCRIPT" "$ROOT_SCRIPT"
install -o root -g root -m 600 "$ARCHIVE" "$ROOT_ARCHIVE"
/bin/bash "$ROOT_SCRIPT" "$ROOT_ARCHIVE" "$EXPECTED_SHA" "$RUN_ID"
WRAPPER_SCRIPT
chown root:root "$WRAPPER"
chmod 755 "$WRAPPER"

printf '%s\n' \
    'github-runner ALL=(root) NOPASSWD: /usr/local/sbin/clickbuild-website-staging-wrapper *' \
    > "$SUDOERS"
chown root:root "$SUDOERS"
chmod 440 "$SUDOERS"
visudo -cf "$SUDOERS"

echo "Installed $WRAPPER with a single-command sudo rule for github-runner."
