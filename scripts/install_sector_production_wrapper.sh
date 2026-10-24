#!/bin/bash
# Install the least-privilege sudo boundary for sector-catalog production deploys.
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || { echo 'Run as root.' >&2; exit 1; }

WRAPPER=/usr/local/sbin/clickbuild-sector-production-wrapper
SUDOERS=/etc/sudoers.d/clickbuild-sector-production
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid

cat > "$WRAPPER" <<'WRAPPER_SCRIPT'
#!/bin/bash
set -Eeuo pipefail
umask 077

EXPECTED_CALLER=github-runner
WORKSPACE=/opt/actions-runner-odoo20/_work/odoo-clickbulid/odoo-clickbulid
SCRIPT="$WORKSPACE/scripts/deploy_sector_catalog_production.sh"
EXPECTED_ARCHIVE=/tmp/clickbuild-sector-production.tar.gz
SCRIPT_ARG=${1:-}
ARCHIVE_ARG=${2:-}
EXPECTED_SHA=${3:-}

[ "${SUDO_USER:-}" = "$EXPECTED_CALLER" ] || { echo 'FAIL: caller must be github-runner' >&2; exit 10; }
[ "$#" -eq 3 ] || { echo 'FAIL: expected SCRIPT ARCHIVE SHA' >&2; exit 11; }
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'FAIL: invalid release SHA' >&2; exit 12; }
[ "$(realpath "$SCRIPT_ARG")" = "$SCRIPT" ] || { echo 'FAIL: unexpected script path' >&2; exit 13; }
[ "$(realpath "$ARCHIVE_ARG")" = "$EXPECTED_ARCHIVE" ] || { echo 'FAIL: unexpected archive path' >&2; exit 14; }
[ "$(git -C "$WORKSPACE" rev-parse HEAD)" = "$EXPECTED_SHA" ] || { echo 'FAIL: checkout SHA mismatch' >&2; exit 15; }

ROOT_SCRIPT=$(mktemp /run/clickbuild-sector-production.XXXXXX)
cleanup() { rm -f "$ROOT_SCRIPT"; }
trap cleanup EXIT
install -o root -g root -m 700 "$SCRIPT" "$ROOT_SCRIPT"
/bin/bash "$ROOT_SCRIPT" "$EXPECTED_ARCHIVE" "$EXPECTED_SHA"
WRAPPER_SCRIPT
chown root:root "$WRAPPER"
chmod 755 "$WRAPPER"

printf '%s\n' \
    'github-runner ALL=(root) NOPASSWD: /usr/local/sbin/clickbuild-sector-production-wrapper *' \
    > "$SUDOERS"
chown root:root "$SUDOERS"
chmod 440 "$SUDOERS"
visudo -cf "$SUDOERS"

echo "Installed $WRAPPER with a single-command sudo rule for github-runner."

