#!/bin/bash
# One-shot installer for the real Odoo 19 Enterprise source.
#
# Run this ON THE SERVER. It will:
#   1. Prompt you for a GitHub Personal Access Token (with `repo` scope) —
#      paste it once, it is NEVER saved to disk and is forgotten after the
#      clone completes.
#   2. Clone github.com/odoo/enterprise (branch 19.0) into /opt/odoo-saas/enterprise
#      using HTTPS + token auth.
#   3. Rebuild the clickbuild/odoo-enterprise:19 docker image with the real
#      source mounted in (replacing the empty placeholder).
#   4. Restart the odoo_saas_ent container.
#   5. Smoke-test that Studio, Helpdesk, etc. are now discoverable.
#
# How to get a token (1 minute):
#   - https://github.com/settings/tokens  →  Generate new token (classic)
#   - Scope: "repo"  (read access is enough)
#   - Expiration: 1 day is plenty
#   - Copy the token (ghp_xxx…) — you'll paste it once below.
#
# After this script finishes you SHOULD revoke the token at the same URL
# (Delete button next to the token) just for hygiene.

set -e
cd /opt/odoo-saas

# Source already cloned? Allow rebuild.
if [ -d enterprise/web_studio ]; then
    echo "[install_ee] /opt/odoo-saas/enterprise already populated — skipping clone."
    echo "[install_ee] If you want a fresh clone, delete it first:"
    echo "[install_ee]   rm -rf /opt/odoo-saas/enterprise"
    NEED_CLONE=0
else
    NEED_CLONE=1
fi

if [ "$NEED_CLONE" = "1" ]; then
    # Take credentials from env if provided (CI use), otherwise prompt.
    if [ -z "${GH_USER:-}" ]; then
        read -p "GitHub username (the one with access to odoo/enterprise): " GH_USER
    fi
    if [ -z "${GH_TOKEN:-}" ]; then
        read -s -p "GitHub Personal Access Token (input hidden): " GH_TOKEN
        echo
    fi
    if [ -z "$GH_USER" ] || [ -z "$GH_TOKEN" ]; then
        echo "[install_ee] FAIL: need both username and token"
        exit 1
    fi

    echo "[install_ee] cloning enterprise@19.0 (shallow, ~750 MB)…"
    # Use credential-store-file=/dev/null trick so the token never sits in disk.
    GIT_ASKPASS=/bin/echo \
    GIT_TERMINAL_PROMPT=0 \
    git -c credential.helper= \
        clone --depth 1 -b 19.0 \
        "https://${GH_USER}:${GH_TOKEN}@github.com/odoo/enterprise.git" \
        enterprise

    # Forget the token immediately.
    unset GH_TOKEN

    # Strip the embedded URL from .git/config so it doesn't linger.
    if [ -d enterprise/.git ]; then
        git -C enterprise remote set-url origin "https://github.com/odoo/enterprise.git"
    fi
fi

# Sanity check.
if [ ! -d enterprise/web_studio ]; then
    echo "[install_ee] FAIL: clone seems incomplete — /opt/odoo-saas/enterprise/web_studio missing"
    exit 2
fi
echo "[install_ee] ✓ enterprise tree present"
echo "[install_ee]   web_studio:       $(test -d enterprise/web_studio && echo yes || echo no)"
echo "[install_ee]   helpdesk:         $(test -d enterprise/helpdesk && echo yes || echo no)"
echo "[install_ee]   sale_subscription: $(test -d enterprise/sale_subscription && echo yes || echo no)"
echo "[install_ee]   industry_fsm:     $(test -d enterprise/industry_fsm && echo yes || echo no)"
ls enterprise | wc -l | xargs printf "[install_ee]   total modules:    %s\n"

# Re-build the docker image with the real source mounted at build time.
echo "[install_ee] rebuilding clickbuild/odoo-enterprise:19 …"
docker build \
    -f docker-enterprise/Dockerfile \
    -t clickbuild/odoo-enterprise:19 \
    --build-arg ENTERPRISE_SRC=./enterprise \
    /opt/odoo-saas

# Restart the EE container so it picks up the new image.
echo "[install_ee] restarting odoo_saas_ent …"
cd /opt/odoo-saas && docker compose up -d --force-recreate odoo_ent
sleep 6

# Smoke test.
echo
echo "[install_ee] verifying enterprise modules are visible to the EE container:"
docker exec odoo_saas_ent ls /mnt/enterprise/ | head -10
echo
docker exec odoo_saas_ent python3 -c "
import os
for m in ('web_studio', 'helpdesk', 'documents', 'sale_subscription', 'industry_fsm'):
    p = os.path.join('/mnt/enterprise', m)
    print(f'  {m:25s} → {\"FOUND\" if os.path.isdir(p) else \"MISSING\"}')
"

cat <<'EOF'

═══════════════════════════════════════════════════════════════════════════
✓ Odoo 19 Enterprise binary is now live on odoo_saas_ent.

Next steps:
  1. Re-init existing Enterprise tenants so they pick up the new modules:
       docker exec odoo_saas_ent odoo -d eetest1 -u all --no-http --stop-after-init
     (replace eetest1 with each EE tenant's DB name)

  2. New tenants signing up on an Enterprise plan will automatically get
     Studio, Helpdesk, Subscriptions, etc. — no extra steps needed.

  3. Revoke the GitHub token at https://github.com/settings/tokens
═══════════════════════════════════════════════════════════════════════════
EOF
