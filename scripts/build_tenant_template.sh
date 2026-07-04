#!/bin/bash
# Build (or rebuild) the tenant template database used for fast provisioning.
#
# Instead of installing ~20 modules from scratch for every signup (2-3 min on
# this VPS), the provisioner clones this template with CREATE DATABASE ...
# TEMPLATE (seconds) and then installs only the sector-specific delta modules.
#
# The template is OWNED BY the 'odoo' postgres role on purpose: the community
# Odoo server connects as 'odoo_community' and only lists databases owned by
# its own role, so the template stays invisible to it — no cron workers, no
# open connections, which CREATE DATABASE ... TEMPLATE requires.
#
# Re-run this script whenever the common module set changes or after updating
# the Cybrosys/OCA bundles so new tenants pick up the new code.
set -euo pipefail

TEMPLATE_DB=tpl_community_core
ODOO_CONTAINER=odoo_saas_app
PG=odoo_saas_postgres
LOG=/var/log/saas-template-build.log

# Common core installed in the template: the intersection used by nearly all
# industry bundles + the Saudi accounting stack every tenant gets anyway.
# Sector-only apps (point_of_sale, fleet, mrp, project, website_sale, medical
# suite, ...) are NOT here — they install as a small delta after cloning.
CORE_MODULES="base,web,mail,contacts,calendar,account,base_accounting_kit,l10n_sa,l10n_sa_edi,sale_management,purchase,stock,crm,hr,hr_holidays,hr_attendance,web_responsive,web_dark_mode,saas_tenant_login_helper,saas_user_limit"

echo "$(date -Is) === building template $TEMPLATE_DB ===" | tee -a "$LOG"

# 1. Drop the old template (never in use — invisible to the app servers).
docker exec "$PG" psql -U odoo -c "DROP DATABASE IF EXISTS $TEMPLATE_DB" >> "$LOG" 2>&1

# 2. Create owned by 'odoo' so odoo_community's db list never shows it.
docker exec "$PG" createdb -U odoo -O odoo "$TEMPLATE_DB" >> "$LOG" 2>&1

# 3. Install the core module set with Arabic loaded, no demo data.
docker exec "$ODOO_CONTAINER" odoo \
    --config=/etc/odoo/odoo.conf \
    -d "$TEMPLATE_DB" \
    -i "$CORE_MODULES" \
    --without-demo=all \
    --load-language=ar_001 \
    --no-http --stop-after-init >> "$LOG" 2>&1 || {
        echo "$(date -Is) TEMPLATE BUILD FAILED — see $LOG" | tee -a "$LOG"
        exit 1
    }

# 4. Localize the template company to Saudi Arabia (country, currency, and
# the sa chart of accounts). Clones inherit this ready-made; non-SA signups
# skip the template and use the classic full-init path instead.
docker exec "$ODOO_CONTAINER" python3 -c '
import odoo
from odoo.tools import config
config.parse_config(["-c", "/etc/odoo/odoo.conf"])
reg = odoo.modules.registry.Registry("'"$TEMPLATE_DB"'")
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    company = env["res.company"].browse(1)
    sa = env["res.country"].search([("code", "=", "SA")], limit=1)
    vals = {"country_id": sa.id}
    if sa.currency_id:
        vals["currency_id"] = sa.currency_id.id
    company.write(vals)
    try:
        # account install may have auto-loaded generic_coa before the company
        # was flagged Saudi — switching template is safe on an empty DB (no
        # journal entries yet), same as Settings -> Fiscal Localization.
        if company.chart_template != "sa":
            env["account.chart.template"].try_loading("sa", company=company, install_demo=False)
        company.env.flush_all()
        print("template: chart is now:", company.chart_template or "?")
    except Exception as e:
        print("template: chart load skipped:", e)
    cr.commit()
' >> "$LOG" 2>&1

# 5. Sanity check + report.
INSTALLED=$(docker exec "$PG" psql -U odoo -d "$TEMPLATE_DB" -tc \
    "select count(*) from ir_module_module where state='installed'" | tr -d ' ')
SIZE=$(docker exec "$PG" psql -U odoo -tc \
    "select pg_size_pretty(pg_database_size('$TEMPLATE_DB'))" | tr -d ' ')
echo "$(date -Is) DONE: $TEMPLATE_DB ready ($INSTALLED modules installed, $SIZE)" | tee -a "$LOG"
