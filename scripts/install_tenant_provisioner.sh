#!/bin/bash
# Installs the host-side tenant provisioner that consumes *.provision.req
# files written by Odoo into /opt/odoo-saas/cert-requests/.
#
# For each request, it:
#   1. Creates a Postgres database matching the subdomain
#   2. Initializes Odoo with base modules into that DB
#   3. Sets the admin user (email/password from the request payload)
#   4. Triggers HTTPS cert provisioning by writing a <sub>.req file
#   5. Notifies the master Odoo DB that the tenant is ready
#
# Sweeper runs via the EXISTING saas-cert-sweeper.timer (every 2 min).
# We just install the provisioner script + extend the sweeper to handle
# .provision.req in addition to .req.
set -e

PROVISIONER=/usr/local/bin/saas-tenant-provisioner.sh
SWEEPER=/usr/local/bin/saas-cert-sweeper.sh

# 1. Install the provisioner itself
cat > "$PROVISIONER" << 'PROV'
#!/bin/bash
# Provision ONE tenant from its JSON request file.
# Usage: saas-tenant-provisioner.sh /path/to/<sub>.provision.req
set -e
REQ="$1"
[ -f "$REQ" ] || { echo "request file not found: $REQ"; exit 2; }
LOG=/var/log/saas-tenant-provisioner.log

read_json() { python3 -c "import json,sys; print(json.load(open('$REQ')).get('$1',''))"; }

SUB=$(read_json subdomain)
TENANT_ID=$(read_json tenant_id)
ADMIN_EMAIL=$(read_json admin_email)
ADMIN_NAME=$(read_json admin_name)
ADMIN_PASSWORD=$(read_json admin_password)
COMPANY=$(read_json company_name)
COMPANY_EMAIL=$(read_json company_email)
COMPANY_PHONE=$(read_json company_phone)
LANG=$(read_json language)
EDITION=$(read_json edition)
COUNTRY=$(read_json customer_country)
# Pick the right container + Postgres role based on edition. Community
# tenants run on odoo_saas_app (db_user odoo_community); Enterprise tenants
# run on odoo_saas_ent (db_user odoo_enterprise). The DB MUST be owned by the
# container's own role: Odoo only lists databases whose owner matches its
# connection user, so a wrong owner makes the tenant invisible to dbfilter
# and /web/login bounces to the (blocked) database selector.
case "$EDITION" in
    enterprise)
        ODOO_CONTAINER=odoo_saas_ent
        DB_OWNER=odoo_enterprise
        ;;
    *)
        ODOO_CONTAINER=odoo_saas_app
        DB_OWNER=odoo_community
        ;;
esac
# Modules to install at first boot. Comma-joined for the -i flag.
MODULES_JSON=$(python3 -c "import json; d=json.load(open('$REQ')); print(','.join(d.get('modules', []) or ['base']))")
INIT_MODULES="${MODULES_JSON:-base,web,mail}"

# Validate subdomain: lowercase alnum + dash
if ! echo "$SUB" | grep -qE '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'; then
    echo "$(date -Is) FAIL invalid subdomain: $SUB" >> "$LOG"
    exit 3
fi

DB="$SUB"
echo "$(date -Is) === provisioning $DB (edition=$EDITION, container=$ODOO_CONTAINER) ===" >> "$LOG"

# 1. Check if DB exists already
if docker exec odoo_saas_postgres psql -U odoo -lqt 2>/dev/null \
        | cut -d'|' -f1 | tr -d ' ' | grep -qx "$DB"; then
    echo "$(date -Is) DB $DB already exists, skipping createdb" >> "$LOG"
else
    docker exec odoo_saas_postgres createdb -U odoo -O "$DB_OWNER" "$DB" >> "$LOG" 2>&1
    echo "$(date -Is) created DB $DB" >> "$LOG"
fi

# 2. Initialize Odoo with the requested module set into the new DB.
# Use --no-http to avoid port conflicts; --stop-after-init exits when done.
# For Enterprise tenants this runs inside odoo_saas_ent so Studio/Helpdesk
# etc. become available; for Community it runs inside odoo_saas_app.
docker exec "$ODOO_CONTAINER" odoo \
    --config=/etc/odoo/odoo.conf \
    -d "$DB" \
    -i "$INIT_MODULES" \
    --without-demo=all \
    --load-language=ar_001 \
    --no-http --stop-after-init >> "$LOG" 2>&1 || {
        echo "$(date -Is) FAIL: odoo init failed for $DB (container=$ODOO_CONTAINER)" >> "$LOG"
        exit 4
    }
echo "$(date -Is) initialized $DB (modules: $INIT_MODULES)" >> "$LOG"

# 3. Set the admin user password + email + name + company.
# Pass values via env vars to avoid heredoc/shell-escape pitfalls.
docker exec \
    -e SAAS_DB="$DB" \
    -e SAAS_ADMIN_EMAIL="$ADMIN_EMAIL" \
    -e SAAS_ADMIN_NAME="$ADMIN_NAME" \
    -e SAAS_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
    -e SAAS_COMPANY="$COMPANY" \
    -e SAAS_COMPANY_EMAIL="${COMPANY_EMAIL:-$ADMIN_EMAIL}" \
    -e SAAS_COMPANY_PHONE="$COMPANY_PHONE" \
    -e SAAS_COUNTRY="${COUNTRY:-SA}" \
    "$ODOO_CONTAINER" python3 -c '
import os, odoo
from odoo.tools import config
config.parse_config(["-c", "/etc/odoo/odoo.conf"])
reg = odoo.modules.registry.Registry(os.environ["SAAS_DB"])
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    admin = env["res.users"].browse(2)
    admin.write({
        "login": os.environ["SAAS_ADMIN_EMAIL"],
        "name":  os.environ["SAAS_ADMIN_NAME"],
        "password": os.environ["SAAS_ADMIN_PASSWORD"],
    })
    company = admin.company_id
    company_vals = {"name": os.environ["SAAS_COMPANY"]}
    # Pre-fill the signup contact details into the company record so the
    # customer finds their email/phone already set in Settings → Companies.
    if os.environ.get("SAAS_COMPANY_EMAIL"):
        company_vals["email"] = os.environ["SAAS_COMPANY_EMAIL"]
    if os.environ.get("SAAS_COMPANY_PHONE"):
        company_vals["phone"] = os.environ["SAAS_COMPANY_PHONE"]
    # Set the company country + currency from the signup choice so the
    # localization (chart of accounts, taxes, ZATCA e-invoicing) applies to
    # the right country. Defaults to Saudi Arabia.
    code = (os.environ.get("SAAS_COUNTRY") or "SA").upper()[:2]
    country = env["res.country"].search([("code", "=", code)], limit=1)
    if country:
        company_vals["country_id"] = country.id
        if country.currency_id:
            company_vals["currency_id"] = country.currency_id.id
    company.write(company_vals)
    # Load the country chart of accounts onto this company if a localization
    # template is available and no chart is installed yet (Odoo 17+ API).
    try:
        if not company.chart_template:
            tmpl = env["account.chart.template"]
            ref = {"SA": "sa", "AE": "ae", "EG": "eg"}.get(code)
            if ref:
                tmpl.try_loading(ref, company=company, install_demo=False)
    except Exception as e:
        print("chart load skipped:", e)
    cr.commit()
    print("admin configured:", admin.login, "/", company.name,
          "/", (country.name if country else "?"))
' >> "$LOG" 2>&1

# 4. Notify the master DB that provisioning succeeded.
docker exec \
    -e SAAS_TENANT_ID="$TENANT_ID" \
    -e SAAS_DB="$DB" \
    odoo_saas_app python3 -c '
import os, odoo
from odoo.tools import config
config.parse_config(["-c", "/etc/odoo/odoo.conf"])
reg = odoo.modules.registry.Registry("odoo")
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    tenant = env["saas.tenant"].browse(int(os.environ["SAAS_TENANT_ID"]))
    if tenant.exists():
        tenant.with_context(bypass_fsm=True).write({
            "api_instance_id": os.environ["SAAS_DB"],
            "state": "trial",
        })
        jobs = env["saas.provisioning.job"].search([
            ("tenant_id", "=", tenant.id),
            ("job_type", "=", "provision"),
            ("state", "=", "running")], limit=1)
        if jobs:
            jobs.write({"state": "completed"})
        cr.commit()
        print("master updated: tenant", tenant.id, "state=trial instance_id=" + os.environ["SAAS_DB"])
' >> "$LOG" 2>&1

# 5. Drop a cert-request so HTTPS gets issued for the subdomain.
# We also include `edition=` so the cert script knows which backend to wire
# up in the per-tenant nginx server block.
REQ_DIR=$(dirname "$REQ")
{
    echo "tenant_id=$TENANT_ID"
    echo "subdomain=$SUB"
    echo "edition=$EDITION"
} > "$REQ_DIR/$SUB.req"
echo "$(date -Is) DONE $DB" >> "$LOG"
PROV
chmod +x "$PROVISIONER"
echo "[provisioner] installed $PROVISIONER"

# 2. Extend the existing sweeper to also handle *.provision.req
cat > "$SWEEPER" << 'SWEEP'
#!/bin/bash
# Unified sweeper:
#   *.provision.req → run saas-tenant-provisioner.sh (creates DB + Odoo + cert)
#   *.req           → run /opt/odoo-saas/provision_tenant_cert.sh (HTTPS only)
set -e
REQ_DIR=/opt/odoo-saas/cert-requests
LOG=/var/log/saas-cert-sweeper.log

shopt -s nullglob

# --- Tenant DB provisioning (priority) ---
for req in "$REQ_DIR"/*.provision.req; do
    sub=$(basename "$req" .provision.req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    echo "$(date -Is) sweeping provision $sub" >> "$LOG"
    if bash /usr/local/bin/saas-tenant-provisioner.sh "$req" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.provision.done"
        echo "$(date -Is) PROVISION DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.provision.error"
        echo "$(date -Is) PROVISION ERROR $sub" >> "$LOG"
    fi
done

# --- HTTPS cert provisioning (after DB exists) ---
for req in "$REQ_DIR"/*.req; do
    # Skip .provision.req which we matched above already
    [[ "$req" == *.provision.req ]] && continue
    sub=$(basename "$req" .req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    echo "$(date -Is) sweeping cert $sub" >> "$LOG"
    if bash /opt/odoo-saas/provision_tenant_cert.sh "$sub" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.done"
        echo "$(date -Is) CERT DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.error"
        echo "$(date -Is) CERT ERROR $sub" >> "$LOG"
    fi
done
SWEEP
chmod +x "$SWEEPER"
echo "[provisioner] updated $SWEEPER to handle both .provision.req and .req"

# 3. Touch the systemd timer just in case
systemctl restart saas-cert-sweeper.timer 2>/dev/null || true
echo "[provisioner] timer state:"
systemctl is-active saas-cert-sweeper.timer
