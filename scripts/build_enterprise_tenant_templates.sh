#!/usr/bin/env bash
# Build plan-specific Odoo Enterprise templates for fast tenant provisioning.
# Each template is owned by the neutral `odoo` role, while its tables remain
# owned by `odoo_enterprise`.  The live Enterprise server therefore cannot
# discover or open templates through dbfilter, but the host provisioner can
# clone them and transfer database ownership to the tenant runtime role.
set -euo pipefail

PG=${PG_CONTAINER:-odoo_saas_postgres}
ODOO=${ENTERPRISE_CONTAINER:-odoo_saas_ent}
PREFIX=${TEMPLATE_PREFIX:-tpl_enterprise}
LOG=${TEMPLATE_BUILD_LOG:-/var/log/saas-enterprise-template-build.log}

STARTER_DB="${PREFIX}_starter"
BUSINESS_DB="${PREFIX}_business"
FULL_DB="${PREFIX}_full"

STARTER_MODULES="base,mail,account,sale,web_studio,helpdesk,documents,sign,l10n_sa,l10n_sa_edi,saas_tenant_login_helper,saas_user_limit"
BUSINESS_DELTA="purchase,stock,crm,project,hr,sale_subscription,marketing_automation,project_forecast"
FULL_DELTA="mrp,point_of_sale,website,industry_fsm,quality,planning,timesheet_grid"

log() {
    printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"
}

drop_db() {
    local db="$1"
    docker exec "$PG" psql -U odoo -d postgres -v ON_ERROR_STOP=1 -c \
        "select pg_terminate_backend(pid) from pg_stat_activity where datname='$db' and pid <> pg_backend_pid();" \
        >>"$LOG" 2>&1
    if [ -n "$(docker exec "$PG" psql -At -U odoo -d postgres -c "select 1 from pg_database where datname='$db'")" ]; then
        docker exec "$PG" psql -U odoo -d postgres -v ON_ERROR_STOP=1 -c \
            "ALTER DATABASE \"$db\" IS_TEMPLATE false;" >>"$LOG" 2>&1
    fi
    docker exec "$PG" dropdb -U odoo --if-exists "$db" >>"$LOG" 2>&1
    docker exec "$ODOO" rm -rf "/var/lib/odoo/filestore/$db" >>"$LOG" 2>&1 || true
}

run_install() {
    local db="$1"
    local modules="$2"
    shift 2
    docker exec "$ODOO" odoo \
        --config=/etc/odoo/odoo.conf \
        -d "$db" -i "$modules" \
        --without-demo=all --no-http --stop-after-init "$@" \
        >>"$LOG" 2>&1
}

clone_template() {
    local source="$1"
    local target="$2"
    local delta="$3"
    drop_db "$target"
    docker exec "$PG" createdb -U odoo -T "$source" -O odoo "$target" \
        >>"$LOG" 2>&1
    docker exec "$ODOO" sh -c \
        "rm -rf /var/lib/odoo/filestore/$target && cp -a /var/lib/odoo/filestore/$source /var/lib/odoo/filestore/$target" \
        >>"$LOG" 2>&1 || true
    run_install "$target" "$delta"
    docker exec "$PG" psql -U odoo -d postgres -v ON_ERROR_STOP=1 -c \
        "ALTER DATABASE \"$target\" OWNER TO odoo;" >>"$LOG" 2>&1
}

validate_template() {
    local db="$1"
    local required="$2"
    local pending missing
    pending=$(docker exec "$PG" psql -At -U odoo -d "$db" -c \
        "select count(*) from ir_module_module where state in ('to install','to upgrade','to remove')")
    missing=$(docker exec "$PG" psql -At -U odoo -d "$db" -c \
        "select string_agg(x.name, ',') from unnest(string_to_array('$required', ',')) x(name) where not exists (select 1 from ir_module_module m where m.name=x.name and m.state='installed')")
    test "$pending" = "0"
    test -z "$missing"
    docker exec "$PG" psql -At -U odoo -d "$db" -c \
        "select '$db'||'|'||count(*)||'|'||pg_database_size('$db') from ir_module_module where state='installed'" \
        | tee -a "$LOG"
}

log "building $STARTER_DB"
drop_db "$FULL_DB"
drop_db "$BUSINESS_DB"
drop_db "$STARTER_DB"
docker exec "$PG" createdb -U odoo -O odoo "$STARTER_DB" >>"$LOG" 2>&1
run_install "$STARTER_DB" "$STARTER_MODULES" --load-language=ar_001

# Preload the Saudi chart once. All three templates inherit it; tenant-specific
# identity, credentials, company details and Enterprise code are still written
# after cloning by the provisioner.
docker exec "$ODOO" python3 -c '
import odoo
from odoo.tools import config
config.parse_config(["-c", "/etc/odoo/odoo.conf"])
reg = odoo.modules.registry.Registry("'"$STARTER_DB"'")
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    company = env["res.company"].browse(1)
    country = env["res.country"].search([("code", "=", "SA")], limit=1)
    vals = {"country_id": country.id}
    if country.currency_id:
        vals["currency_id"] = country.currency_id.id
    company.write(vals)
    if company.chart_template != "sa":
        env["account.chart.template"].try_loading("sa", company=company, install_demo=False)
    cr.commit()
' >>"$LOG" 2>&1
docker exec "$PG" psql -U odoo -d postgres -v ON_ERROR_STOP=1 -c \
    "ALTER DATABASE \"$STARTER_DB\" OWNER TO odoo;" >>"$LOG" 2>&1
validate_template "$STARTER_DB" "$STARTER_MODULES"

log "building $BUSINESS_DB from $STARTER_DB"
clone_template "$STARTER_DB" "$BUSINESS_DB" "$BUSINESS_DELTA"
validate_template "$BUSINESS_DB" "$STARTER_MODULES,$BUSINESS_DELTA"

log "building $FULL_DB from $BUSINESS_DB"
clone_template "$BUSINESS_DB" "$FULL_DB" "$FULL_DELTA"
validate_template "$FULL_DB" "$STARTER_MODULES,$BUSINESS_DELTA,$FULL_DELTA"

log "Enterprise templates ready"

# Hide templates from Odoo cron workers (Odoo list_dbs skips datistemplate).
for db in "$STARTER_DB" "$BUSINESS_DB" "$FULL_DB"; do
    docker exec "$PG" psql -U odoo -d postgres -v ON_ERROR_STOP=1 -c \
        "ALTER DATABASE \"$db\" IS_TEMPLATE true;" >>"$LOG" 2>&1
done
