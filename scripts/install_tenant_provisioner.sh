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
INDUSTRY=$(read_json industry)
DEMO_SECTOR=$(read_json demo_sector)
MAX_USERS=$(read_json max_users)
ENTERPRISE_CODE=$(read_json enterprise_code)
LANG=$(read_json language)
EDITION=$(read_json edition)
PLAN_CODE=$(read_json plan_code)
COUNTRY=$(read_json customer_country)
IS_DEMO=$(read_json is_demo)
DEMO_EXPIRES_AT=$(read_json demo_expires_at)
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

# -- Enterprise: official Odoo modules only ----------------------------------
# Enterprise tenants run under an Odoo Enterprise subscription. Install ONLY
# official Odoo modules (Community core in the image + Enterprise apps under
# /mnt/enterprise) plus our own platform glue (saas_*). Any external
# third-party addon (OCA under /mnt/oca, Cybrosys under /mnt/cybrosys, other
# vendor addons) is dropped here: it either clashes with an Enterprise native
# or is not covered by the subscription. Community tenants are untouched.
if [ "$EDITION" = "enterprise" ]; then
    EE_OFFICIAL=$(docker exec "$ODOO_CONTAINER" sh -c 'ls /usr/lib/python3/dist-packages/odoo/addons /mnt/enterprise 2>/dev/null' | sort -u)
    EE_KEPT=""; EE_DROPPED=""
    for m in $(echo "$INIT_MODULES" | tr ',' ' '); do
        case "$m" in
            saas_*) EE_KEPT="$EE_KEPT,$m" ;;
            *) if grep -Fqx -- "$m" <<<"$EE_OFFICIAL"; then EE_KEPT="$EE_KEPT,$m"; else EE_DROPPED="$EE_DROPPED $m"; fi ;;
        esac
    done
    INIT_MODULES="${EE_KEPT#,}"
    [ -n "$EE_DROPPED" ] && echo "$(date -Is) enterprise: dropped non-official (third-party) modules:$EE_DROPPED" >> "$LOG"
fi

# Validate subdomain: lowercase alnum + dash
if ! echo "$SUB" | grep -qE '^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$'; then
    echo "$(date -Is) FAIL invalid subdomain: $SUB" >> "$LOG"
    exit 3
fi

FINAL_DB="$SUB"
# Provision under a temporary, non-servable name so no web request can load a
# half-built registry while modules install (that caused "could not serialize
# access due to concurrent update" crashes when the tenant URL was opened
# mid-provisioning). Renamed to the real subdomain at the very end.
DB="prov_${SUB}_$$"
echo "$(date -Is) === provisioning $FINAL_DB as $DB (edition=$EDITION, container=$ODOO_CONTAINER) ===" >> "$LOG"

# 1. Create the tenant DB — fast path clones the prebuilt template.
# The template (built by build_tenant_template.sh) already contains the
# common core + Saudi accounting stack, so cloning takes seconds instead of
# a 2-3 minute full module install. Conditions for the fast path:
#   - community edition (enterprise runs a different module set/container)
#   - Saudi customer (the template company is localized to SA; other
#     countries need their own chart of accounts → classic full init)
#   - the template database actually exists
TEMPLATE_DB=tpl_community_core
POOL_REGEX='^pool_([0-9a-f]{8}|ce_[0-9a-f]{8})$'
if [ "$EDITION" = "enterprise" ]; then
    case "$PLAN_CODE" in
        starter_ee)    TEMPLATE_DB=tpl_enterprise_starter;  POOL_REGEX='^pool_ee_starter_[0-9a-f]{8}$' ;;
        business_ee)   TEMPLATE_DB=tpl_enterprise_business; POOL_REGEX='^pool_ee_business_[0-9a-f]{8}$' ;;
        enterprise_ee) TEMPLATE_DB=tpl_enterprise_full;     POOL_REGEX='^pool_ee_full_[0-9a-f]{8}$' ;;
        *)             TEMPLATE_DB=tpl_enterprise_starter;  POOL_REGEX='^pool_ee_starter_[0-9a-f]{8}$' ;;
    esac
fi
CLONED=0
BUILD_CRON_IDS=""
db_exists() {
    local db="$1"
    docker exec odoo_saas_postgres psql -At -U odoo -d postgres -c \
        "select 1 from pg_database where datname='$db'" 2>/dev/null | grep -qx 1
}
template_exists() { db_exists "$TEMPLATE_DB"; }

# Odoo's main Enterprise workers enumerate every database owned by their role
# for cron processing, including temporary prov_* databases. Suspend only the
# jobs that were active while a tenant is being built, then restore those exact
# jobs after the atomic rename. This prevents schedulers from racing module
# installation, demo seeding and ALTER DATABASE.
disable_build_crons() {
    local has_table active_ids
    has_table=$(docker exec odoo_saas_postgres psql -U odoo -d "$DB" -Atc \
        "select to_regclass('public.ir_cron') is not null" 2>/dev/null || true)
    [ "$has_table" = "t" ] || return 0
    active_ids=$(docker exec odoo_saas_postgres psql -U odoo -d "$DB" \
        -v ON_ERROR_STOP=1 -Atc \
        "select coalesce(string_agg(id::text, ','), '')
           from ir_cron where active")
    if [ -n "$active_ids" ]; then
        BUILD_CRON_IDS=$(printf '%s,%s' "$BUILD_CRON_IDS" "$active_ids" \
            | tr ',' '\n' | sed '/^$/d' | sort -n -u | paste -sd, -)
        docker exec odoo_saas_postgres psql -U odoo -d "$DB" \
            -v ON_ERROR_STOP=1 -c \
            "update ir_cron set active=false where id in ($active_ids);" \
            >>"$LOG" 2>&1
        echo "$(date -Is) suspended build crons for $DB: $active_ids" >>"$LOG"
    fi
}

# Exact Enterprise cache: the first request for a plan+industry module set
# installs its delta from the tier template, then stores a clean pre-customer
# snapshot. Every matching request after that clones the exact snapshot and
# skips module installation. The tier template OID is part of the key, so a
# template rebuild automatically invalidates older caches without a risky
# in-place migration.
CACHE_DB=""
CACHE_HIT=0
CACHE_GENERATION="ee-sector-cycles-19.0.3"
if [ "$EDITION" = "enterprise" ] && [ "${COUNTRY:-SA}" = "SA" ] && db_exists "$TEMPLATE_DB"; then
    TEMPLATE_OID=$(docker exec odoo_saas_postgres psql -At -U odoo -d postgres -c \
        "select oid from pg_database where datname='$TEMPLATE_DB'")
    NORMALIZED_MODULES=$(printf '%s' "$INIT_MODULES" | tr ',' '\n' | sed '/^$/d' | sort -u | paste -sd, -)
    CACHE_KEY=$(printf '%s' "$CACHE_GENERATION|$TEMPLATE_DB|$TEMPLATE_OID|${COUNTRY:-SA}|$NORMALIZED_MODULES" \
        | sha256sum | cut -c1-16)
    CACHE_DB="tpl_ee_cache_$CACHE_KEY"
    if db_exists "$CACHE_DB"; then
        TEMPLATE_DB="$CACHE_DB"
        POOL_REGEX='a^'
        CACHE_HIT=1
        echo "$(date -Is) enterprise cache hit: $CACHE_DB" >>"$LOG"
    fi
fi

# Warm-pool fast path: grab a pre-cloned DB by renaming it to the tenant
# subdomain (instant) instead of cloning the template on the critical path.
# Pool DBs (pool_*) are owned by 'odoo' with no connections, so the rename is
# safe. Returns 0 on success; caller falls back to a normal clone on failure.
grab_pool_db() {
    local pooldb
    pooldb=$(docker exec odoo_saas_postgres psql -U odoo -tAc \
        "select datname from pg_database where datname ~ '$POOL_REGEX' order by datname limit 1" 2>/dev/null | tr -d ' ')
    [ -z "$pooldb" ] && return 1
    docker exec odoo_saas_postgres psql -U odoo -v ON_ERROR_STOP=1 -c \
        "ALTER DATABASE \"$pooldb\" RENAME TO \"$DB\"; ALTER DATABASE \"$DB\" OWNER TO $DB_OWNER;" >> "$LOG" 2>&1 || return 1
    docker exec "$ODOO_CONTAINER" sh -c \
        "rm -rf /var/lib/odoo/filestore/$DB; mv /var/lib/odoo/filestore/$pooldb /var/lib/odoo/filestore/$DB 2>/dev/null || cp -a /var/lib/odoo/filestore/$TEMPLATE_DB /var/lib/odoo/filestore/$DB" >> "$LOG" 2>&1
    echo "$(date -Is) grabbed pool db $pooldb -> $DB" >> "$LOG"
    return 0
}
if docker exec odoo_saas_postgres psql -U odoo -lqt 2>/dev/null \
        | cut -d'|' -f1 | tr -d ' ' | grep -qx "$DB"; then
    echo "$(date -Is) DB $DB already exists, skipping createdb" >> "$LOG"
elif [ "${COUNTRY:-SA}" = "SA" ] && template_exists; then
    if grab_pool_db; then
        CLONED=1
        # Refill the pool in the background so the next signup is instant too.
        ( bash /usr/local/bin/saas_warm_pool.sh >/dev/null 2>&1 & )
    else
        docker exec odoo_saas_postgres createdb -U odoo -T "$TEMPLATE_DB" -O "$DB_OWNER" "$DB" >> "$LOG" 2>&1
        # The DB references attachments stored on disk under the template's
        # filestore — clone that too or images/attachments 404 in the new tenant.
        docker exec "$ODOO_CONTAINER" sh -c \
            "rm -rf /var/lib/odoo/filestore/$DB && cp -a /var/lib/odoo/filestore/$TEMPLATE_DB /var/lib/odoo/filestore/$DB" >> "$LOG" 2>&1 \
            || echo "$(date -Is) WARN: filestore clone failed for $DB" >> "$LOG"
        CLONED=1
        echo "$(date -Is) cloned DB $DB from $TEMPLATE_DB (with filestore)" >> "$LOG"
    fi
else
    docker exec odoo_saas_postgres createdb -U odoo -O "$DB_OWNER" "$DB" >> "$LOG" 2>&1
    echo "$(date -Is) created DB $DB" >> "$LOG"
fi
disable_build_crons

# 2. Install modules.
# Fast path: only the delta between the requested set and what the template
# already ships. Classic path: the full requested set from scratch.
run_odoo_install() {
    local modules="$1"
    local load_language="${2:-0}"
    local attempt=1 attempt_log
    attempt_log=$(mktemp)
    while [ "$attempt" -le 3 ]; do
        local args=(--config=/etc/odoo/odoo.conf -d "$DB" -i "$modules"
                    --without-demo=all --no-http --stop-after-init)
        [ "$load_language" = "1" ] && args+=(--load-language=ar_001)
        if docker exec "$ODOO_CONTAINER" odoo "${args[@]}" >"$attempt_log" 2>&1; then
            cat "$attempt_log" >>"$LOG"
            rm -f "$attempt_log"
            return 0
        fi
        cat "$attempt_log" >>"$LOG"
        if grep -q "could not serialize access due to concurrent update" "$attempt_log" && [ "$attempt" -lt 3 ]; then
            echo "$(date -Is) retry: transient PostgreSQL serialization conflict for $DB (attempt $attempt/3)" >>"$LOG"
            sleep $((attempt * 2))
            attempt=$((attempt + 1))
            continue
        fi
        rm -f "$attempt_log"
        return 1
    done
}

if [ "$CLONED" = "1" ]; then
    INSTALLED=$(docker exec odoo_saas_postgres psql -U odoo -d "$DB" -tAc \
        "select string_agg(name, ',') from ir_module_module where state in ('installed','to install','to upgrade')")
    MISSING=$(python3 -c "
requested = [m.strip() for m in '''$INIT_MODULES'''.split(',') if m.strip()]
installed = set('''$INSTALLED'''.split(','))
print(','.join([m for m in requested if m not in installed]))")
    if [ -n "$MISSING" ]; then
        run_odoo_install "$MISSING" || {
                echo "$(date -Is) FAIL: delta install failed for $DB (modules: $MISSING)" >> "$LOG"
                exit 4
            }
        echo "$(date -Is) initialized $DB (delta modules: $MISSING)" >> "$LOG"
    else
        echo "$(date -Is) initialized $DB (template covered all modules)" >> "$LOG"
    fi
    disable_build_crons

    # Cache only a real delta and do it before tenant credentials, UUID,
    # company details or Enterprise code are written. A concurrent request may
    # win the same cache name; that is safe and should not fail provisioning.
    if [ "$EDITION" = "enterprise" ] && [ "$CACHE_HIT" = "0" ] \
            && [ -n "$CACHE_DB" ] && [ -n "$MISSING" ] && ! db_exists "$CACHE_DB"; then
        if docker exec odoo_saas_postgres createdb -U odoo -T "$DB" -O odoo "$CACHE_DB" >>"$LOG" 2>&1; then
            if [ -n "$BUILD_CRON_IDS" ]; then
                docker exec odoo_saas_postgres psql -U odoo -d "$CACHE_DB" \
                    -v ON_ERROR_STOP=1 -c \
                    "update ir_cron set active=true where id in ($BUILD_CRON_IDS);" \
                    >>"$LOG" 2>&1
            fi
            docker exec "$ODOO_CONTAINER" sh -c \
                "rm -rf /var/lib/odoo/filestore/$CACHE_DB && cp -a /var/lib/odoo/filestore/$DB /var/lib/odoo/filestore/$CACHE_DB" \
                >>"$LOG" 2>&1 || true
            # Odoo cron workers poll every DB list_dbs returns; flagging the cache
            # as a template hides it (list_dbs skips datistemplate), so no idle
            # connection can block a later CREATE DATABASE ... TEMPLATE.
            docker exec odoo_saas_postgres psql -U odoo -d postgres -c \
                "ALTER DATABASE \"$CACHE_DB\" IS_TEMPLATE true;" >>"$LOG" 2>&1
            echo "$(date -Is) enterprise cache created: $CACHE_DB" >>"$LOG"
        elif db_exists "$CACHE_DB"; then
            echo "$(date -Is) enterprise cache created by concurrent request: $CACHE_DB" >>"$LOG"
        else
            echo "$(date -Is) WARN: enterprise cache creation failed: $CACHE_DB" >>"$LOG"
        fi
    fi
else
    run_odoo_install "$INIT_MODULES" 1 || {
            echo "$(date -Is) FAIL: odoo init failed for $DB (container=$ODOO_CONTAINER)" >> "$LOG"
            exit 4
        }
    echo "$(date -Is) initialized $DB (modules: $INIT_MODULES)" >> "$LOG"
    disable_build_crons
fi

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
    -e SAAS_INDUSTRY="${DEMO_SECTOR:-${INDUSTRY:-other}}" \
    -e SAAS_COUNTRY="${COUNTRY:-SA}" \
    -e SAAS_CLONED="$CLONED" \
    -e SAAS_MAX_USERS="${MAX_USERS:-0}" \
    -e SAAS_ENTERPRISE_CODE="$ENTERPRISE_CODE" \
    -e SAAS_IS_DEMO="${IS_DEMO:-false}" \
    -e SAAS_DEMO_EXPIRES_AT="$DEMO_EXPIRES_AT" \
    "$ODOO_CONTAINER" python3 -c '
import os, odoo
from odoo.tools import config
config.parse_config(["-c", "/etc/odoo/odoo.conf"])
reg = odoo.modules.registry.Registry(os.environ["SAAS_DB"])
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    # Cloned DBs share the template identity — give each tenant its own
    # database uuid/secret so sessions, tokens and instance identity never
    # collide across tenants.
    if os.environ.get("SAAS_CLONED") == "1":
        import uuid, secrets as pysecrets
        from odoo import fields as ofields
        icp = env["ir.config_parameter"].sudo()
        icp.set_param("database.uuid", str(uuid.uuid4()))
        icp.set_param("database.secret", pysecrets.token_hex(16))
        icp.set_param("database.create_date", ofields.Datetime.now())
    # Plan seat limit, enforced in-tenant by the saas_user_limit module.
    max_users = (os.environ.get("SAAS_MAX_USERS") or "0").strip()
    if max_users.isdigit() and int(max_users) > 0:
        env["ir.config_parameter"].sudo().set_param("saas.max_users", max_users)
    # Odoo Enterprise subscription code — links the tenant to the partner
    # Odoo contract so Enterprise stays licensed and users are reported.
    ent_code = (os.environ.get("SAAS_ENTERPRISE_CODE") or "").strip()
    if ent_code:
        env["ir.config_parameter"].sudo().set_param("database.enterprise_code", ent_code)
    # Demo sandbox: never allow a trial database to contact real customers or
    # charge real payment methods. These restrictions are applied before the
    # temporary database is renamed to its public subdomain.
    is_demo = (os.environ.get("SAAS_IS_DEMO") or "").strip().lower() in ("1", "true", "yes")
    if is_demo:
        icp = env["ir.config_parameter"].sudo()
        icp.set_param("saas.demo_mode", "true")
        icp.set_param("saas.demo.outbound_blocked", "true")
        icp.set_param("saas.demo.expires_at", os.environ.get("SAAS_DEMO_EXPIRES_AT") or "")
        if "ir.mail_server" in env:
            env["ir.mail_server"].sudo().search([]).write({"active": False})
        if "payment.provider" in env:
            providers = env["payment.provider"].sudo().search([("state", "!=", "disabled")])
            if providers:
                providers.write({"state": "disabled"})
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
    # Load the country chart of accounts onto this company. account install
    # may have auto-loaded generic_coa before the country was set — switching
    # on a fresh tenant (no journal entries) is safe, same as the Settings ->
    # Fiscal Localization picker (Odoo 17+ API).
    try:
        tmpl = env["account.chart.template"]
        ref = {"SA": "sa", "AE": "ae", "EG": "eg"}.get(code)
        if ref and company.chart_template != ref:
            tmpl.try_loading(ref, company=company, install_demo=False)
    except Exception as e:
        print("chart load skipped:", e)
    # Give the tenant admin the manager role of sector modules that hide
    # behind their own security groups, so the app is usable on first login.
    SECTOR_ADMIN_GROUPS = ["trailer_inspection_saso.group_trailer_inspection_user", "trailer_inspection_saso.group_trailer_inspector", "trailer_inspection_saso.group_trailer_reviewer", "trailer_inspection_saso.group_trailer_manager"]
    gfld = "group_ids" if "group_ids" in admin._fields else "groups_id"
    for xmlid in SECTOR_ADMIN_GROUPS:
        grp = env.ref(xmlid, raise_if_not_found=False)
        if grp:
            admin.write({gfld: [(4, grp.id)]})
            print("granted admin group:", xmlid)
    # Give sector apps that ship without a web icon a recognizable tile
    # (their root menu is otherwise an unlabeled icon in the apps grid).
    troot = env.ref("trailer_inspection_saso.menu_trailer_root", raise_if_not_found=False)
    if troot and not troot.web_icon:
        troot.write({"web_icon": "fleet,static/description/icon.png"})
    # Build a coherent, sector-aware business cycle only inside isolated
    # Enterprise demos. The seeder is idempotent and refuses normal tenants.
    if is_demo and "saas.demo.seed" in env:
        summary = env["saas.demo.seed"].sudo().seed_demo_cycle(
            os.environ.get("SAAS_INDUSTRY") or "other")
        print("demo business cycle seeded:", summary)
    cr.commit()
    print("admin configured:", admin.login, "/", company.name,
          "/", (country.name if country else "?"))
' >> "$LOG" 2>&1

# 3b. Rename the fully-built DB to its real subdomain (instant). Until now it
# had a non-servable name, so the module install could not be disturbed by a
# web worker. Drop any stale leftover of the same subdomain from a previous
# failed attempt first.
if docker exec odoo_saas_postgres psql -U odoo -tAc "select 1 from pg_database where datname='$FINAL_DB'" 2>/dev/null | grep -qx 1; then
    docker exec odoo_saas_postgres dropdb -U odoo --force --if-exists "$FINAL_DB" >> "$LOG" 2>&1
    docker exec "$ODOO_CONTAINER" rm -rf "/var/lib/odoo/filestore/$FINAL_DB" >> "$LOG" 2>&1 || true
fi

# Freeze the temporary DB before rename. The Enterprise web connection pool
# can otherwise discover it between initialization and ALTER DATABASE.
docker exec odoo_saas_postgres psql -U odoo -d postgres -v ON_ERROR_STOP=1 \
    -c "ALTER DATABASE \"$DB\" WITH ALLOW_CONNECTIONS false;" >>"$LOG" 2>&1
docker exec odoo_saas_postgres psql -U odoo -d postgres -v ON_ERROR_STOP=1 \
    -c "select pg_terminate_backend(pid) from pg_stat_activity where datname='$DB' and pid <> pg_backend_pid();" \
    >>"$LOG" 2>&1
docker exec odoo_saas_postgres psql -U odoo -d postgres -v ON_ERROR_STOP=1 \
    -c "ALTER DATABASE \"$DB\" RENAME TO \"$FINAL_DB\";" >>"$LOG" 2>&1 || {
        docker exec odoo_saas_postgres psql -U odoo -d postgres \
            -c "ALTER DATABASE \"$DB\" WITH ALLOW_CONNECTIONS true;" >>"$LOG" 2>&1 || true
        echo "$(date -Is) FAIL: rename $DB -> $FINAL_DB" >>"$LOG"
        exit 5
    }
docker exec "$ODOO_CONTAINER" sh -c "rm -rf /var/lib/odoo/filestore/$FINAL_DB; mv /var/lib/odoo/filestore/$DB /var/lib/odoo/filestore/$FINAL_DB 2>/dev/null || true" >> "$LOG" 2>&1
docker exec odoo_saas_postgres psql -U odoo -d postgres -v ON_ERROR_STOP=1 \
    -c "ALTER DATABASE \"$FINAL_DB\" WITH ALLOW_CONNECTIONS true;" >>"$LOG" 2>&1
DB="$FINAL_DB"
if [ -n "$BUILD_CRON_IDS" ]; then
    docker exec odoo_saas_postgres psql -U odoo -d "$DB" \
        -v ON_ERROR_STOP=1 -c \
        "update ir_cron
            set active=true,
                nextcall=greatest(
                    coalesce(nextcall, now() at time zone 'UTC'),
                    (now() at time zone 'UTC') + interval '5 minutes'
                        + ((id % 30) * interval '10 seconds'))
          where id in ($BUILD_CRON_IDS);" \
        >>"$LOG" 2>&1
    echo "$(date -Is) restored and staggered tenant crons for $DB: $BUILD_CRON_IDS" >>"$LOG"
fi
# Enterprise: the publisher-warranty job's schedule is cloned from the
# template, so a new tenant would keep the template's stale expiration date
# (shown as "database expired") until that job's next weekly run. Run it now
# so Odoo sets the tenant's real expiration straight away. Non-fatal.
if [ "$EDITION" = "enterprise" ]; then
    docker exec odoo_saas_postgres psql -U odoo -d "$DB" -c \
        "update ir_cron set nextcall = now() at time zone 'UTC'
          where id = (select res_id from ir_model_data
                      where module = 'mail' and name = 'ir_cron_module_update_notification');" \
        >>"$LOG" 2>&1 || true
    echo "$(date -Is) enterprise: publisher warranty check scheduled now for $DB" >>"$LOG"
fi
echo "$(date -Is) renamed provisioning DB -> $FINAL_DB" >> "$LOG"

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
        tenant_values = {
            "api_instance_id": os.environ["SAAS_DB"],
            "state": "trial",
        }
        if "demo_sandbox_state" in tenant._fields and getattr(tenant, "is_demo", False):
            tenant_values["demo_sandbox_state"] = "enforced"
        tenant.with_context(bypass_fsm=True).write(tenant_values)
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
NGINX_TENANTS=/opt/odoo-saas/nginx-tenants

shopt -s nullglob

nginx_reload() {
    if docker exec odoo_saas_nginx nginx -t >/dev/null 2>&1; then
        docker exec odoo_saas_nginx nginx -s reload >/dev/null 2>&1
        return 0
    fi
    return 1
}

# Write a "subscription expired" vhost for a suspended tenant. Same certs
# and server_name as the live conf, but every request gets a bilingual
# renewal page instead of the Odoo proxy. The tenant DB stays untouched.
write_suspended_conf() {
    local sub="$1"
    cat <<NGINXBLOCK
server {
    listen 443 ssl http2;
    server_name $sub.odoo.clickbulid.com;
    ssl_certificate     /etc/letsencrypt/live/$sub.odoo.clickbulid.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$sub.odoo.clickbulid.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    location / {
        default_type "text/html; charset=utf-8";
        return 402 "<!doctype html><html dir=\"rtl\" lang=\"ar\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>الاشتراك منتهي — Subscription Expired</title><style>body{font-family:Tahoma,Arial,sans-serif;background:#f5f3ff;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}.card{background:#fff;border-radius:16px;box-shadow:0 10px 40px rgba(109,40,217,.12);padding:48px;max-width:520px;text-align:center;margin:16px}h1{color:#6d28d9;font-size:1.6rem;margin:0 0 12px}p{color:#475569;line-height:1.9}a.btn{display:inline-block;background:#6d28d9;color:#fff;text-decoration:none;padding:14px 36px;border-radius:10px;font-weight:bold;margin-top:18px}small{color:#94a3b8;display:block;margin-top:22px}</style></head><body><div class=\"card\"><div style=\"font-size:3rem\">⏸️</div><h1>انتهت الفترة التجريبية / الاشتراك</h1><p>تم إيقاف مساحة العمل الخاصة بك مؤقتاً لعدم تجديد الاشتراك.<br>بياناتك محفوظة بالكامل — جدّد الآن لاستعادة الوصول فوراً.</p><p style=\"direction:ltr\">Your workspace is paused because the subscription was not renewed.<br>Your data is safe — renew now to restore access instantly.</p><a class=\"btn\" href=\"https://odoo.clickbulid.com/pricing\">جدّد اشتراكك الآن — Renew Now</a><small>ClickBuild · support@clickbuild.com</small></div></body></html>";
    }
}
NGINXBLOCK
}

# --- Tenant destruction (runs first so delete-then-recreate works) ---
for req in "$REQ_DIR"/*.delete.req; do
    sub=$(basename "$req" .delete.req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    echo "$(date -Is) sweeping delete $sub" >> "$LOG"
    if bash /usr/local/bin/saas-tenant-destroyer.sh "$req" >> "$LOG" 2>&1; then
        rm -f "$req" "$NGINX_TENANTS/$sub.conf.live-orig"
        echo "$(date -Is) DELETE DONE $sub" >> "$LOG"
    else
        mv "$req" "$REQ_DIR/$sub.delete.error"
        echo "$(date -Is) DELETE ERROR $sub" >> "$LOG"
    fi
done

# --- Tenant suspension (swap vhost for the renewal page) ---
for req in "$REQ_DIR"/*.suspend.req; do
    sub=$(basename "$req" .suspend.req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    conf="$NGINX_TENANTS/$sub.conf"
    if [ -f "$conf" ] && [ ! -f "$conf.live-orig" ]; then
        cp "$conf" "$conf.live-orig"
        write_suspended_conf "$sub" > "$conf"
        if nginx_reload; then
            echo "$(date -Is) SUSPENDED $sub" >> "$LOG"
        else
            mv "$conf.live-orig" "$conf"
            nginx_reload || true
            echo "$(date -Is) SUSPEND ERROR $sub (nginx test failed, conf restored)" >> "$LOG"
        fi
    else
        echo "$(date -Is) SUSPEND skipped for $sub (no conf or already suspended)" >> "$LOG"
    fi
    rm -f "$req"
done

# --- Seat limit sync (admin changed the purchased user count) ---
for req in "$REQ_DIR"/*.seats.req; do
    sub=$(basename "$req" .seats.req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    limit=$(python3 -c "import json; print(int(json.load(open('$req')).get('max_users', 0)))" 2>/dev/null || echo 0)
    if docker exec -e SEATS_DB="$sub" -e SEATS_LIMIT="$limit" odoo_saas_app python3 -c '
import os, odoo
from odoo.tools import config
config.parse_config(["-c", "/etc/odoo/odoo.conf"])
reg = odoo.modules.registry.Registry(os.environ["SEATS_DB"])
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    env["ir.config_parameter"].sudo().set_param("saas.max_users", os.environ["SEATS_LIMIT"])
    cr.commit()
    print("seats set:", os.environ["SEATS_DB"], "->", os.environ["SEATS_LIMIT"])
' >> "$LOG" 2>&1; then
        echo "$(date -Is) SEATS $sub -> $limit" >> "$LOG"
    else
        echo "$(date -Is) SEATS ERROR $sub" >> "$LOG"
    fi
    rm -f "$req"
done

# --- Tenant resume (restore the original proxy vhost) ---
for req in "$REQ_DIR"/*.resume.req; do
    sub=$(basename "$req" .resume.req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    conf="$NGINX_TENANTS/$sub.conf"
    if [ -f "$conf.live-orig" ]; then
        mv "$conf.live-orig" "$conf"
        nginx_reload || true
        echo "$(date -Is) RESUMED $sub" >> "$LOG"
    else
        echo "$(date -Is) RESUME skipped for $sub (not suspended)" >> "$LOG"
    fi
    rm -f "$req"
done

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
    # Skip request types handled by the dedicated loops above
    [[ "$req" == *.provision.req ]] && continue
    [[ "$req" == *.suspend.req ]] && continue
    [[ "$req" == *.resume.req ]] && continue
    [[ "$req" == *.delete.req ]] && continue
    [[ "$req" == *.seats.req ]] && continue
    sub=$(basename "$req" .req)
    sub=$(echo "$sub" | tr -cd 'a-z0-9-')
    [ -z "$sub" ] && { rm -f "$req"; continue; }
    echo "$(date -Is) sweeping cert $sub" >> "$LOG"
    if bash /opt/odoo-saas/provision_tenant_cert.sh "$sub" >> "$LOG" 2>&1; then
        mv "$req" "$REQ_DIR/$sub.done"
        echo "$(date -Is) CERT DONE $sub" >> "$LOG"
        # provision_tenant_cert.sh regenerates a LIVE proxy conf — if the
        # tenant is currently suspended, re-apply the block page so a cert
        # renewal can never silently unblock an unpaid tenant.
        if [ -f "$NGINX_TENANTS/$sub.conf.live-orig" ]; then
            cp "$NGINX_TENANTS/$sub.conf" "$NGINX_TENANTS/$sub.conf.live-orig"
            write_suspended_conf "$sub" > "$NGINX_TENANTS/$sub.conf"
            nginx_reload || true
            echo "$(date -Is) CERT: re-applied suspension for $sub" >> "$LOG"
        fi
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
