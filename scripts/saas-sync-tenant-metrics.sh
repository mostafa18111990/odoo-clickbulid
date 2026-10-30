#!/usr/bin/env bash
# Synchronize active tenant metrics across the Odoo 19 and Odoo 20 planes.
set -euo pipefail

MASTER_PG=${MASTER_PG_CONTAINER:-odoo_saas_postgres}
PG20=${ODOO20_PG_CONTAINER:-odoo_saas_postgres20}
PG_USER=${PG_USER:-odoo}
MASTER_DB=${MASTER_DB:-odoo}
BACKUP_ROOT=${BACKUP_ROOT:-/opt/backups}
DRY_RUN=${DRY_RUN:-0}
TENANT_DB_FILTER=${TENANT_DB_FILTER:-}
ODOO19_CONTAINERS=(odoo_saas_app odoo_saas_ent)
ODOO20_CONTAINERS=(odoo_saas_20_community odoo_saas_20_enterprise)

log() { printf '%s %s\n' "$(date -Is)" "$*"; }
container_exists() { docker inspect "$1" >/dev/null 2>&1; }
psql_master() { docker exec "$MASTER_PG" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$MASTER_DB" "$@"; }

db_exists() {
    local container="$1" db="$2"
    container_exists "$container" &&
        docker exec "$container" psql -At -U "$PG_USER" -d postgres \
            -c "select 1 from pg_database where datname='$db'" 2>/dev/null | grep -qx 1
}

find_db_container() {
    local db="$1"
    if db_exists "$PG20" "$db"; then
        printf '%s\n' "$PG20"
    elif db_exists "$MASTER_PG" "$db"; then
        printf '%s\n' "$MASTER_PG"
    else
        return 1
    fi
}

filestore_bytes() {
    local db="$1" plane="$2" container bytes
    local -a candidates
    if [[ "$plane" == "$PG20" ]]; then
        candidates=("${ODOO20_CONTAINERS[@]}")
    else
        candidates=("${ODOO19_CONTAINERS[@]}")
    fi
    for container in "${candidates[@]}"; do
        container_exists "$container" || continue
        if docker exec "$container" test -d "/var/lib/odoo/filestore/$db" 2>/dev/null; then
            bytes=$(docker exec "$container" du -sb "/var/lib/odoo/filestore/$db" | awk '{print $1}')
            printf '%s\n' "${bytes:-0}"
            return
        fi
    done
    printf '0\n'
}

mark_error() {
    local tenant_id="$1" reason="$2"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "dry-run tenant=$tenant_id status=error reason=$reason"
    else
        psql_master -Atc \
            "update saas_tenant set metrics_synced_at=now(),metrics_sync_status='error',metrics_sync_error='$reason' where id=$tenant_id" \
            >/dev/null
    fi
}

now_epoch=$(date +%s)
synced=0
failed=0
tenant_rows=$(psql_master -At -F '|' -c \
    "select id,coalesce(api_instance_id,''),coalesce(edition,'community'),coalesce(external_server_id,0)
       from saas_tenant
      where state in ('trial','pending_payment','active','grace_period','suspended')
        and api_instance_id is not null and api_instance_id not like 'pending:%'
      order by id")

while IFS='|' read -r tenant_id db_name edition external_server_id; do
    [[ -n "$tenant_id" ]] || continue
    [[ -z "$TENANT_DB_FILTER" || "$db_name" == "$TENANT_DB_FILTER" ]] || continue
    if [[ "$external_server_id" != "0" ]]; then
        mark_error "$tenant_id" external_server_metrics_not_configured
        failed=$((failed + 1))
        continue
    fi
    if [[ ! "$db_name" =~ ^[A-Za-z0-9_-]+$ ]]; then
        mark_error "$tenant_id" invalid_database_identifier
        failed=$((failed + 1))
        continue
    fi
    if ! plane=$(find_db_container "$db_name"); then
        mark_error "$tenant_id" database_unavailable
        failed=$((failed + 1))
        continue
    fi
    if ! db_bytes=$(docker exec "$plane" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres -Atc \
            "select pg_database_size('$db_name')" 2>/dev/null); then
        mark_error "$tenant_id" database_size_query_failed
        failed=$((failed + 1))
        continue
    fi
    if ! users_count=$(docker exec "$plane" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$db_name" -Atc \
            "select count(*) from res_users where active is true and coalesce(share,false) is false" 2>/dev/null); then
        mark_error "$tenant_id" users_query_failed
        failed=$((failed + 1))
        continue
    fi

    fs_bytes=$(filestore_bytes "$db_name" "$plane")
    total_bytes=$((db_bytes + fs_bytes))
    backup_status=missing
    last_backup_sql=NULL
    latest_backup=$(find "$BACKUP_ROOT" -mindepth 2 -maxdepth 3 -type f -name "$db_name.dump" \
        -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)
    if [[ -n "$latest_backup" ]]; then
        backup_epoch=$(stat -c %Y "$latest_backup")
        backup_timestamp=$(date -u -d "@$backup_epoch" '+%Y-%m-%d %H:%M:%S')
        last_backup_sql="'$backup_timestamp'::timestamp"
        backup_status=ok
        (( now_epoch - backup_epoch <= 129600 )) || backup_status=stale
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log "dry-run db=$db_name plane=$plane users=$users_count backup=$backup_status"
    else
        psql_master -Atc \
            "update saas_tenant set
                users_count=$users_count,
                disk_usage_mb=round(($db_bytes::numeric / 1048576),2),
                filestore_usage_mb=round(($fs_bytes::numeric / 1048576),2),
                total_storage_mb=round(($total_bytes::numeric / 1048576),2),
                last_backup=$last_backup_sql,
                backup_sync_status='$backup_status',
                metrics_synced_at=now(),metrics_sync_status='ok',metrics_sync_error=null
              where id=$tenant_id" >/dev/null
        log "synced db=$db_name plane=$plane users=$users_count backup=$backup_status"
    fi
    synced=$((synced + 1))
done <<< "$tenant_rows"

log "metrics synchronization finished synced=$synced failed=$failed dry_run=$DRY_RUN"
[[ "$failed" -eq 0 ]]
