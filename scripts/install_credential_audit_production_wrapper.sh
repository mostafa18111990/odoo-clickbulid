#!/usr/bin/env bash
# Run once as root on the production host.
set -Eeuo pipefail
umask 077

[[ "$(id -u)" == 0 ]] || {
    echo 'FAIL: run this installer as root' >&2
    exit 10
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_wrapper="$script_dir/clickbuild-credential-audit-production-wrapper.sh"
target_wrapper=/usr/local/sbin/clickbuild-credential-audit-production-wrapper
sudoers_file=/etc/sudoers.d/clickbuild-credential-audit-production

[[ -f "$source_wrapper" ]] || exit 11
bash -n "$source_wrapper"

install -o root -g root -m 755 "$source_wrapper" "$target_wrapper"
tmp_sudoers=$(mktemp /run/clickbuild-credential-audit-sudoers.XXXXXX)
cleanup() { rm -f -- "$tmp_sudoers"; }
trap cleanup EXIT
printf '%s\n' \
    'github-runner ALL=(root) NOPASSWD: /usr/local/sbin/clickbuild-credential-audit-production-wrapper *' \
    >"$tmp_sudoers"
chmod 440 "$tmp_sudoers"
visudo -cf "$tmp_sudoers" >/dev/null
install -o root -g root -m 440 "$tmp_sudoers" "$sudoers_file"
visudo -cf "$sudoers_file" >/dev/null

echo 'CREDENTIAL_AUDIT_WRAPPER_INSTALLED'
