#!/usr/bin/env bash
# Synchronize tenant usage and backup status into the master Odoo database.
# Safe defaults target the ClickBuild production Docker Compose stack. Set
# DRY_RUN=1 and optionally TENANT_DB_FILTER=<db> to validate without writes.
set -euo pipefail

PG_CONTAINER=${PG_CONTAINER:-odoo_saas_postgres}
PG_USER=${PG_USER:-odoo}
MASTER_DB=${MASTER_DB:-odoo}
BACKUP_ROOT=${BACKUP_ROOT:-/opt/backups}
COMMUNITY_VOLUME=${COMMUNITY_VOLUME:-odoo-saas_odoo_data}
ENTERPRISE_VOLUME=${ENTERPRISE_VOLUME:-odoo-saas_odoo_ent_data}
DRY_RUN=${DRY_RUN:-0}
TENANT_DB_FILTER=${TENANT_DB_FILTER:-}

log() { printf '%s %s\n' "$(date -Is)" "$*"; }

psql_master() {
    docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$MASTER_DB" "$@"
}

mark_error() {
    local tenant_id="$1"
    local error_code="$2"
    if [[ "$DRY_RUN" == "1" ]]; then
        log "dry-run tenant=$tenant_id status=error reason=$error_code"
        return
    fi
    psql_master -Atc \
        "UPDATE saas_tenant SET metrics_synced_at=now(), metrics_sync_status='error', metrics_sync_error='$error_code' WHERE id=$tenant_id" \
        >/dev/null
}

community_root=$(docker volume inspect "$COMMUNITY_VOLUME" -f '{{.Mountpoint}}')
enterprise_root=$(docker volume inspect "$ENTERPRISE_VOLUME" -f '{{.Mountpoint}}')
now_epoch=$(date +%s)
synced=0
failed=0

tenant_rows=$(psql_master -At -F '|' -c \
    "SELECT id,COALESCE(api_instance_id,''),COALESCE(edition,'community'),COALESCE(external_server_id,0)
       FROM saas_tenant
      WHERE state IN ('trial','pending_payment','active','grace_period','suspended')
        AND api_instance_id IS NOT NULL
        AND api_instance_id NOT LIKE 'pending:%'
      ORDER BY id")

while IFS='|' read -r tenant_id db_name edition external_server_id; do
    [[ -n "$tenant_id" ]] || continue
    if [[ -n "$TENANT_DB_FILTER" && "$db_name" != "$TENANT_DB_FILTER" ]]; then
        continue
    fi
    if [[ "$external_server_id" != "0" ]]; then
        mark_error "$tenant_id" "external_server_metrics_not_configured"
        failed=$((failed + 1))
        continue
    fi
    if [[ ! "$db_name" =~ ^[a-zA-Z0-9_]+$ ]]; then
        mark_error "$tenant_id" "invalid_database_identifier"
        failed=$((failed + 1))
        continue
    fi

    if ! db_bytes=$(docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d postgres -Atc \
        "SELECT pg_database_size('$db_name')" 2>/dev/null); then
        mark_error "$tenant_id" "database_unavailable"
        failed=$((failed + 1))
        continue
    fi
    if ! users_count=$(docker exec "$PG_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$PG_USER" -d "$db_name" -Atc \
        "SELECT count(*) FROM res_users WHERE active IS TRUE AND COALESCE(share,FALSE) IS FALSE" 2>/dev/null); then
        mark_error "$tenant_id" "users_query_failed"
        failed=$((failed + 1))
        continue
    fi

    preferred_root="$community_root"
    [[ "$edition" == "enterprise" ]] && preferred_root="$enterprise_root"
    filestore_path="$preferred_root/filestore/$db_name"
    if [[ ! -d "$filestore_path" && -d "$community_root/filestore/$db_name" ]]; then
        filestore_path="$community_root/filestore/$db_name"
    elif [[ ! -d "$filestore_path" && -d "$enterprise_root/filestore/$db_name" ]]; then
        filestore_path="$enterprise_root/filestore/$db_name"
    fi
    filestore_bytes=0
    [[ -d "$filestore_path" ]] && filestore_bytes=$(du -sb "$filestore_path" | awk '{print $1}')
    total_bytes=$((db_bytes + filestore_bytes))

    backup_status=missing
    last_backup_sql=NULL
    latest_backup=$(find "$BACKUP_ROOT" -mindepth 2 -maxdepth 2 -type f -name "$db_name.dump" \
        -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2- || true)
    if [[ -n "$latest_backup" ]]; then
        backup_epoch=$(stat -c %Y "$latest_backup")
        backup_timestamp=$(date -u -d "@$backup_epoch" '+%Y-%m-%d %H:%M:%S')
        last_backup_sql="'$backup_timestamp'::timestamp"
        backup_status=ok
        if (( now_epoch - backup_epoch > 129600 )); then
            backup_status=stale
        fi
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log "dry-run db=$db_name users=$users_count db_bytes=$db_bytes filestore_bytes=$filestore_bytes backup=$backup_status"
    else
        psql_master -Atc \
            "UPDATE saas_tenant
                SET users_count=$users_count,
                    disk_usage_mb=round(($db_bytes::numeric / 1048576), 2),
                    filestore_usage_mb=round(($filestore_bytes::numeric / 1048576), 2),
                    total_storage_mb=round(($total_bytes::numeric / 1048576), 2),
                    last_backup=$last_backup_sql,
                    backup_sync_status='$backup_status',
                    metrics_synced_at=now(),
                    metrics_sync_status='ok',
                    metrics_sync_error=NULL
              WHERE id=$tenant_id" >/dev/null
        log "synced db=$db_name users=$users_count backup=$backup_status"
    fi
    synced=$((synced + 1))
done <<< "$tenant_rows"

latest_master_backup=$(find "$BACKUP_ROOT" -mindepth 2 -maxdepth 2 -type f -name "$MASTER_DB.dump" \
    -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2- || true)
if [[ "$DRY_RUN" != "1" && -n "$latest_master_backup" ]]; then
    master_backup_epoch=$(stat -c %Y "$latest_master_backup")
    master_backup_date=$(date -u -d "@$master_backup_epoch" '+%Y-%m-%d')
    psql_master -Atc \
        "INSERT INTO ir_config_parameter (key,value,create_uid,write_uid,create_date,write_date)
         VALUES ('saas.last_backup_date','$master_backup_date',1,1,now(),now())
         ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value,write_uid=1,write_date=now()" \
        >/dev/null
fi

log "metrics synchronization finished synced=$synced failed=$failed dry_run=$DRY_RUN"
[[ "$failed" -eq 0 ]]
