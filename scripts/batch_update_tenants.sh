#!/bin/bash
# Batch-update Odoo modules across ALL tenant databases (rolling update).
#
# Usage:
#   saas-batch-update.sh <module1,module2> [options]
#
# Options:
#   --edition community|enterprise|all   which tenants to touch (default: all)
#   --tenants sub1,sub2                  only these subdomains
#   --dry-run                            list what would run, change nothing
#
# Behaviour:
#   - Tenants are read from the master DB (every state that still has a
#     database: trial/active/pending_payment/grace_period/suspended/
#     cancelled/archived). Deleted tenants are skipped.
#   - Databases are updated ONE AT A TIME (the VPS has 2GB RAM).
#   - A failed update is retried once, then reported; the batch continues.
#   - The community template DB (tpl_community_core) is updated at the end
#     so newly provisioned tenants get the same module versions.
#
# Example:
#   saas-batch-update.sh base_accounting_kit,saas_user_limit
#   saas-batch-update.sh point_of_sale --edition community
set -uo pipefail

MODULES="${1:-}"
[ -z "$MODULES" ] && { echo "Usage: $0 <module1,module2> [--edition ...] [--tenants ...] [--dry-run]"; exit 1; }
shift || true

EDITION_FILTER="all"
ONLY_TENANTS=""
DRY_RUN=0
while [ $# -gt 0 ]; do
    case "$1" in
        --edition) EDITION_FILTER="$2"; shift 2 ;;
        --tenants) ONLY_TENANTS="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PG=odoo_saas_postgres
LOG=/var/log/saas-batch-update.log
TEMPLATE_DB=tpl_community_core

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

# Tenant list from the master DB: subdomain|edition
TENANTS=$(docker exec "$PG" psql -U odoo -d odoo -tAc \
    "SELECT subdomain || '|' || COALESCE(edition, 'community')
     FROM saas_tenant
     WHERE state NOT IN ('deleted', 'lead')
     ORDER BY subdomain")

PASS=(); FAIL=(); SKIP=()

log "=== BATCH UPDATE start: modules=[$MODULES] edition=$EDITION_FILTER dry_run=$DRY_RUN ==="

update_db() {
    local db="$1" container="$2"
    docker exec "$container" odoo \
        --config=/etc/odoo/odoo.conf \
        -d "$db" \
        -u "$MODULES" \
        --no-http --stop-after-init >> "$LOG" 2>&1
}

for entry in $TENANTS; do
    sub="${entry%%|*}"
    edition="${entry##*|}"

    # Filters
    if [ -n "$ONLY_TENANTS" ] && ! echo ",$ONLY_TENANTS," | grep -q ",$sub,"; then
        continue
    fi
    if [ "$EDITION_FILTER" != "all" ] && [ "$edition" != "$EDITION_FILTER" ]; then
        SKIP+=("$sub (edition)")
        continue
    fi
    # Database must actually exist
    if ! docker exec "$PG" psql -U odoo -lqt 2>/dev/null | cut -d'|' -f1 | tr -d ' ' | grep -qx "$sub"; then
        SKIP+=("$sub (no db)")
        continue
    fi

    case "$edition" in
        enterprise) container=odoo_saas_ent ;;
        *)          container=odoo_saas_app ;;
    esac

    if [ "$DRY_RUN" = "1" ]; then
        log "DRY: would update $sub ($edition) in $container"
        continue
    fi

    log "updating $sub ($edition) ..."
    if update_db "$sub" "$container"; then
        PASS+=("$sub")
        log "OK   $sub"
    else
        log "RETRY $sub ..."
        if update_db "$sub" "$container"; then
            PASS+=("$sub (retry)")
            log "OK   $sub (on retry)"
        else
            FAIL+=("$sub")
            log "FAIL $sub — see $LOG"
        fi
    fi
done

# Keep the provisioning template in sync so new tenants get the update too.
if [ "$DRY_RUN" = "0" ] && [ "$EDITION_FILTER" != "enterprise" ]; then
    if docker exec "$PG" psql -U odoo -lqt 2>/dev/null | cut -d'|' -f1 | tr -d ' ' | grep -qx "$TEMPLATE_DB"; then
        log "updating template $TEMPLATE_DB ..."
        if update_db "$TEMPLATE_DB" odoo_saas_app; then
            log "OK   template"
        else
            log "FAIL template — new tenants keep old versions until fixed!"
            FAIL+=("$TEMPLATE_DB")
        fi
    fi
fi

log "=== BATCH UPDATE done: ok=${#PASS[@]} failed=${#FAIL[@]} skipped=${#SKIP[@]} ==="
[ ${#PASS[@]} -gt 0 ] && log "  OK:      ${PASS[*]}"
[ ${#FAIL[@]} -gt 0 ] && log "  FAILED:  ${FAIL[*]}"
[ ${#SKIP[@]} -gt 0 ] && log "  SKIPPED: ${SKIP[*]}"
[ ${#FAIL[@]} -eq 0 ]
