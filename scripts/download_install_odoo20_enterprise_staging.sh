#!/usr/bin/env bash
# Securely download the licensed official Odoo 20 Enterprise Debian package
# without placing the subscription code in shell history or process arguments.
set -Eeuo pipefail
umask 077

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
INSTALLER="$ROOT_DIR/scripts/install_odoo20_enterprise_staging.sh"
CURL_CONFIG=$(mktemp /tmp/odoo20-enterprise-curl.XXXXXX)
DOWNLOAD_PATH=$(mktemp --suffix=.deb /tmp/odoo20-enterprise.XXXXXX)

cleanup() {
    rm -f -- "$CURL_CONFIG" "$DOWNLOAD_PATH"
}
trap cleanup EXIT

[ "$(id -u)" -eq 0 ] || { echo "FAIL: run as root" >&2; exit 1; }
command -v curl >/dev/null || { echo "FAIL: curl is not installed" >&2; exit 1; }
command -v dpkg-deb >/dev/null || { echo "FAIL: dpkg-deb is not installed" >&2; exit 1; }
[ -f "$INSTALLER" ] || { echo "FAIL: Enterprise staging installer is missing" >&2; exit 1; }

read -r -s -p "Odoo Enterprise subscription code: " SUBSCRIPTION_CODE
echo
[[ "$SUBSCRIPTION_CODE" =~ ^M[0-9]{6,32}$ ]] \
    || { unset SUBSCRIPTION_CODE; echo "FAIL: invalid subscription code format" >&2; exit 1; }

{
    printf 'url = "https://www.odoo.com/thanks/download"\n'
    printf 'get\n'
    printf 'data-urlencode = "code=%s"\n' "$SUBSCRIPTION_CODE"
    printf 'data-urlencode = "platform_version=deb_20e"\n'
} >"$CURL_CONFIG"
unset SUBSCRIPTION_CODE

echo "Downloading the official Odoo 20 Enterprise package..."
curl --fail --location --silent --show-error \
    --config "$CURL_CONFIG" --output "$DOWNLOAD_PATH"
rm -f -- "$CURL_CONFIG"
CURL_CONFIG=""

dpkg-deb --info "$DOWNLOAD_PATH" >/dev/null \
    || { echo "FAIL: Odoo did not return a valid Debian package" >&2; exit 1; }

bash "$INSTALLER" "$DOWNLOAD_PATH"
