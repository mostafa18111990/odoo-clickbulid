#!/bin/bash
# Install a curated set of Cybrosys Odoo 19 accounting + utility modules.
#
# Clones github.com/CybroOdoo/CybroAddons (branch 19.0) into
# /opt/odoo-saas/cybrosys/ and mounts it into both containers
# alongside the OCA bundle already installed.
#
# Idempotent — safe to re-run to add new modules.
set -euo pipefail

CYBROSYS_ROOT=/opt/odoo-saas/cybrosys
REPO_URL="https://github.com/CybroOdoo/CybroAddons.git"
BRANCH="19.0"
COMPOSE=/opt/odoo-saas/docker-compose.yml

# ── 1. Clone / update the repo (sparse checkout — we pick only what we need) ─
mkdir -p "$CYBROSYS_ROOT"
REPO_DIR="$CYBROSYS_ROOT/CybroAddons"

if [ -d "$REPO_DIR/.git" ]; then
    echo "[cybrosys] Repo already cloned — pulling latest …"
    git -C "$REPO_DIR" fetch --depth 1 origin "$BRANCH" 2>&1 | tail -2 || true
    git -C "$REPO_DIR" reset --hard "origin/$BRANCH" 2>&1 | tail -1 || true
else
    echo "[cybrosys] Shallow-cloning CybroAddons@${BRANCH} (sparse) …"
    git clone --depth 1 -b "$BRANCH" --no-checkout "$REPO_URL" "$REPO_DIR"
    git -C "$REPO_DIR" sparse-checkout init --cone
fi

# ── Modules to include (edit this list to add more) ─────────────────────────
MODULES=(
    base_accounting_kit
    base_account_budget
    account_day_book
    account_discount_journal_entry
    account_report_send_by_mail
    account_interest_on_overdue_invoice
    account_budget_limit_alert
    account_line_view
    cw_account
    # Healthcare sector bundle — auto-installed for industry=healthcare tenants.
    base_hospital_management
    dental_clinical_management
    medical_lab_management
)

echo "[cybrosys] Checking out ${#MODULES[@]} modules …"
git -C "$REPO_DIR" sparse-checkout set "${MODULES[@]}"
git -C "$REPO_DIR" checkout "$BRANCH" -- 2>&1 | tail -2 || true

# ── Patch known upstream bugs (re-applied after every pull/reset) ────────────
# base_hospital_management's pharmacy_dashboard.css ships two syntax errors
# (`padding-top:1.6rem:` colon-for-semicolon, and an extra closing brace).
# Browsers tolerate both but rtlcss aborts, which kills the whole Arabic RTL
# asset bundle: tenants then render with the ugly fallback style and show
# "A css error occured" in the backend.
PHARMACY_CSS="$REPO_DIR/base_hospital_management/static/src/css/pharmacy_dashboard.css"
if [ -f "$PHARMACY_CSS" ]; then
    sed -i 's/padding-top:1\.6rem:/padding-top:1.6rem;/' "$PHARMACY_CSS"
    # Drop any unbalanced extra closing braces (idempotent rewrite).
    python3 - "$PHARMACY_CSS" <<'PYFIX'
import sys
path = sys.argv[1]
out, depth = [], 0
for line in open(path):
    keep = []
    for ch in line:
        if ch == '{':
            depth += 1
        elif ch == '}':
            if depth == 0:
                continue  # extra brace — drop it
            depth -= 1
        keep.append(ch)
    out.append(''.join(keep))
open(path, 'w').write(''.join(out))
PYFIX
    echo "[cybrosys] patched pharmacy_dashboard.css rtlcss-breaking syntax"
fi

# Make world-readable for the odoo user inside containers.
chmod -R a+rX "$CYBROSYS_ROOT"

# ── 2. Confirm modules are present ───────────────────────────────────────────
echo
echo "[cybrosys] Modules checked out:"
for m in "${MODULES[@]}"; do
    if [ -f "$REPO_DIR/$m/__manifest__.py" ]; then
        echo "  ✓ $m"
    else
        echo "  ✗ $m  ← NOT FOUND (may not exist in 19.0)"
    fi
done

# ── 3. Mount /mnt/cybrosys into both containers ───────────────────────────────
patch_volume() {
    local svc=$1
    if grep -A 40 "container_name: $svc" "$COMPOSE" | grep -q '/mnt/cybrosys'; then
        echo "  ✓ $svc already mounts /mnt/cybrosys"
        return
    fi
    python3 - "$COMPOSE" "$svc" << 'PY'
import sys, re
path, svc = sys.argv[1], sys.argv[2]
with open(path) as f: c = f.read()
# Find the service block
pat = re.compile(r'(container_name: ' + re.escape(svc) + r'.*?)(\n  [a-z_]+:|\Z)', re.DOTALL)
m = pat.search(c)
assert m, f'service block for {svc} not found'
block = m.group(1)
# Insert after the /mnt/oca mount (or extra-addons if oca not present)
anchor = r'(- \./oca:/mnt/oca:ro\n)'
if re.search(anchor, block):
    new_block = re.sub(anchor, r'\1      - ./cybrosys:/mnt/cybrosys:ro\n', block, count=1)
else:
    new_block = re.sub(
        r'(- \./addons:/mnt/extra-addons\n)',
        r'\1      - ./cybrosys:/mnt/cybrosys:ro\n',
        block, count=1)
assert new_block != block, 'anchor mount line not found in service block'
c = c[:m.start(1)] + new_block + c[m.end(1):]
with open(path, 'w') as f: f.write(c)
print(f'  patched compose service {svc}')
PY
}

cp "$COMPOSE" "$COMPOSE.bak.cybrosys.$(date +%s)"
echo
echo "[cybrosys] Patching docker-compose.yml …"
patch_volume odoo_saas_app
patch_volume odoo_saas_ent

# ── 4. Add /mnt/cybrosys/CybroAddons to addons_path in both confs ────────────
CYBROSYS_PATH="/mnt/cybrosys/CybroAddons"

patch_addons_path() {
    local conf=$1
    if grep -q "$CYBROSYS_PATH" "$conf"; then
        echo "  ✓ $(basename $conf) already has cybrosys path"
        return
    fi
    sed -i "s|^addons_path = \(.*\)|addons_path = \1,$CYBROSYS_PATH|" "$conf"
    echo "  ✓ extended addons_path in $(basename $conf)"
}

echo
echo "[cybrosys] Updating addons_path …"
patch_addons_path /opt/odoo-saas/config/odoo.conf
[ -f /opt/odoo-saas/docker-enterprise/odoo-enterprise.conf ] \
    && patch_addons_path /opt/odoo-saas/docker-enterprise/odoo-enterprise.conf

# ── 5. Recreate containers ────────────────────────────────────────────────────
echo
echo "[cybrosys] Recreating containers …"
cd /opt/odoo-saas
docker compose up -d --force-recreate odoo_saas_app odoo_saas_ent
echo "  Waiting 10s for Odoo to start …"
sleep 10

# ── 6. Refresh apps list in master DB ────────────────────────────────────────
echo
echo "[cybrosys] Refreshing apps list in master DB …"
docker exec odoo_saas_app python3 -c "
import odoo
from odoo.tools import config
config.parse_config(['-c', '/etc/odoo/odoo.conf'])
reg = odoo.modules.registry.Registry('odoo')
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    env['ir.module.module'].update_list()
    cr.commit()
    kit = env['ir.module.module'].search([('name', '=', 'base_accounting_kit')])
    if kit:
        print(f'  base_accounting_kit state: {kit.state}')
    else:
        print('  base_accounting_kit NOT found — check path')
    n = env['ir.module.module'].search_count([])
    print(f'  Total modules known to master DB: {n}')
" 2>&1 | grep -vE 'WARNING|DEBUG|tools.config|modules.loading' | tail -5

# ── 7. Smoke-install base_accounting_kit on logintest tenant ─────────────────
echo
echo "[cybrosys] Smoke-installing base_accounting_kit on logintest DB …"
docker exec odoo_saas_app python3 -c "
import odoo
from odoo.tools import config
config.parse_config(['-c', '/etc/odoo/odoo.conf'])
reg = odoo.modules.registry.Registry('logintest')
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    mod = env['ir.module.module'].search([('name', '=', 'base_accounting_kit')])
    if not mod:
        print('  ✗ base_accounting_kit not found — addons_path issue?')
    elif mod.state == 'installed':
        print('  ✓ base_accounting_kit already installed')
    else:
        mod.button_immediate_install()
        cr.commit()
        mod.invalidate_recordset()
        print(f'  ✓ base_accounting_kit state={mod.state}')
" 2>&1 | grep -vE 'WARNING|DEBUG|tools.config|modules.loading' | grep -E '✓|✗|state=|ERROR' || echo "  (check logs above)"

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "═══════════════════════════════════════════════════════════════════════"
echo " ✓ Cybrosys Accounting bundle installed"
echo "═══════════════════════════════════════════════════════════════════════"
echo " Modules added:"
for m in "${MODULES[@]}"; do
    [ -f "$REPO_DIR/$m/__manifest__.py" ] && echo "   ✓ $m" || echo "   ✗ $m (missing)"
done
echo
echo " Next: Go to any tenant → Apps → search 'Accounting Kit'"
echo "       OR: Apps → Update Apps List, then install base_accounting_kit"
echo "═══════════════════════════════════════════════════════════════════════"
