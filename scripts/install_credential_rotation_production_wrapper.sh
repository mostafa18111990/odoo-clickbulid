#!/usr/bin/env bash
# Run once as root on the production host after this release is merged.
set -Eeuo pipefail
umask 077

[[ "$(id -u)" == 0 ]] || { echo 'FAIL: run as root' >&2; exit 10; }
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_wrapper="$script_dir/clickbuild-credential-rotation-production-wrapper.sh"
target_wrapper=/usr/local/sbin/clickbuild-credential-rotation-production-wrapper
sudoers_file=/etc/sudoers.d/clickbuild-credential-rotation-production
[[ -f "$source_wrapper" ]] || exit 11
bash -n "$source_wrapper"
install -o root -g root -m 755 "$source_wrapper" "$target_wrapper"
temporary=$(mktemp /run/clickbuild-credential-rotation-sudoers.XXXXXX)
cleanup() { rm -f -- "$temporary"; }
trap cleanup EXIT
printf '%s\n' \
    'github-runner ALL=(root) NOPASSWD: /usr/local/sbin/clickbuild-credential-rotation-production-wrapper *' \
    >"$temporary"
chmod 440 "$temporary"
visudo -cf "$temporary" >/dev/null
install -o root -g root -m 440 "$temporary" "$sudoers_file"
visudo -cf "$sudoers_file" >/dev/null
echo 'CREDENTIAL_ROTATION_WRAPPER_INSTALLED'
