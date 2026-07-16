#!/usr/bin/env bash
# Maintain isolated warm pools for Community and every Enterprise plan tier.
# A pool database is already a template clone; provisioning only renames it,
# changes ownership and applies tenant-specific identity/configuration.
set -uo pipefail

COMMUNITY_POOL_SIZE=${SAAS_POOL_SIZE:-3}
ENTERPRISE_POOL_SIZE=${SAAS_ENTERPRISE_POOL_SIZE:-2}
PG=odoo_saas_postgres
LOG=/var/log/saas-warm-pool.log

log() { printf '%s %s\n' "$(date -Is)" "$*" >>"$LOG"; }

db_exists() {
    local db="$1"
    docker exec "$PG" psql -At -U odoo -d postgres -c \
        "select 1 from pg_database where datname='$db'" 2>/dev/null | grep -qx 1
}

pool_count() {
    local regex="$1"
    docker exec "$PG" psql -At -U odoo -d postgres -c \
        "select count(*) from pg_database where datname ~ '$regex'" 2>/dev/null | tr -d ' '
}

fill_pool() {
    local template="$1" prefix="$2" regex="$3" container="$4" target="$5"
    local have name
    if ! db_exists "$template"; then
        log "template $template missing; pool $prefix skipped"
        return 0
    fi
    have=$(pool_count "$regex"); have=${have:-0}
    log "pool $prefix maintenance: have=$have target=$target template=$template"
    while [ "$have" -lt "$target" ]; do
        name="${prefix}_$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
        if docker exec "$PG" createdb -U odoo -T "$template" -O odoo "$name" >>"$LOG" 2>&1; then
            docker exec "$container" sh -c \
                "rm -rf /var/lib/odoo/filestore/$name && cp -a /var/lib/odoo/filestore/$template /var/lib/odoo/filestore/$name" \
                >>"$LOG" 2>&1 || true
            log "created pool db $name from $template"
            have=$((have + 1))
        else
            log "FAILED to create pool db $name from $template"
            return 1
        fi
    done
}

# The Community regex also consumes the three legacy pool_<hex> databases.
fill_pool tpl_community_core pool_ce '^pool_([0-9a-f]{8}|ce_[0-9a-f]{8})$' \
    odoo_saas_app "$COMMUNITY_POOL_SIZE"
fill_pool tpl_enterprise_starter pool_ee_starter '^pool_ee_starter_[0-9a-f]{8}$' \
    odoo_saas_ent "$ENTERPRISE_POOL_SIZE"
fill_pool tpl_enterprise_business pool_ee_business '^pool_ee_business_[0-9a-f]{8}$' \
    odoo_saas_ent "$ENTERPRISE_POOL_SIZE"
fill_pool tpl_enterprise_full pool_ee_full '^pool_ee_full_[0-9a-f]{8}$' \
    odoo_saas_ent "$ENTERPRISE_POOL_SIZE"

log "pool maintenance complete"
