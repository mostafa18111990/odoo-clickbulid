#!/usr/bin/env bash
# Daily verified backup of the master/tenant databases and both filestores.
set -euo pipefail
umask 077

BACKUP_ROOT=/opt/backups
DAY=$(date +%F)
TS=$(date +%Y%m%d_%H%M%S)
DAY_DIR="$BACKUP_ROOT/$DAY"
PG_CONTAINER=odoo_saas_postgres
ODOO_CONTAINERS=(odoo_saas_app odoo_saas_ent)

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

mkdir -p "$DAY_DIR"
chmod 700 "$DAY_DIR"
log "=== Starting verified backup into $DAY_DIR ==="

mapfile -t DBS < <(docker exec "$PG_CONTAINER" psql -At -U odoo -d postgres -c \
  "select datname from pg_database where datallowconn and not datistemplate and datname <> 'postgres' and datname not like 'tpl\_%' and datname not like 'pool\_%' and datname not like 'prov\_%' and datname not like 'stage\_%' order by datname")
if [ "${#DBS[@]}" -eq 0 ]; then
    log "FAILED: database inventory is empty"
    exit 10
fi

TOTAL_DB=0
TOTAL_FS=0
FAIL=0

for DB in "${DBS[@]}"; do
    if ! [[ "$DB" =~ ^[A-Za-z0-9_-]+$ ]]; then
        log "FAILED: unsafe database name"
        FAIL=$((FAIL + 1))
        continue
    fi
    log "Backing up database: $DB"
    DB_FILE="$DAY_DIR/$DB.dump"
    TMP_DB_FILE="$DAY_DIR/.$DB.dump.$TS.tmp"
    if docker exec "$PG_CONTAINER" pg_dump -Fc -U odoo -d "$DB" >"$TMP_DB_FILE" \
       && test -s "$TMP_DB_FILE" \
       && docker exec -i "$PG_CONTAINER" pg_restore --list <"$TMP_DB_FILE" >/dev/null; then
        mv "$TMP_DB_FILE" "$DB_FILE"
        chmod 600 "$DB_FILE"
        log "  OK DB: $(basename "$DB_FILE") ($(du -h "$DB_FILE" | cut -f1))"
        TOTAL_DB=$((TOTAL_DB + 1))
    else
        log "  FAILED DB: $DB"
        rm -f "$TMP_DB_FILE"
        FAIL=$((FAIL + 1))
        continue
    fi

    FS_FILE="$DAY_DIR/${DB}_filestore.tar.gz"
    TMP_FS_FILE="$DAY_DIR/.${DB}_filestore.$TS.tmp"
    found=0
    for container in "${ODOO_CONTAINERS[@]}"; do
        if docker exec "$container" test -d "/var/lib/odoo/filestore/$DB" 2>/dev/null; then
            found=1
            if docker exec "$container" tar -czf - -C /var/lib/odoo/filestore "$DB" \
                 >"$TMP_FS_FILE" 2>/dev/null \
               && test -s "$TMP_FS_FILE" \
               && tar -tzf "$TMP_FS_FILE" >/dev/null; then
                mv "$TMP_FS_FILE" "$FS_FILE"
                chmod 600 "$FS_FILE"
                log "  OK filestore: $(basename "$FS_FILE") ($(du -h "$FS_FILE" | cut -f1))"
                TOTAL_FS=$((TOTAL_FS + 1))
            else
                log "  FAILED filestore: $DB"
                rm -f "$TMP_FS_FILE"
                FAIL=$((FAIL + 1))
            fi
            break
        fi
    done
    if [ "$found" -eq 0 ]; then
        log "  WARN no filestore directory: $DB"
    fi
done

if [ "$FAIL" -eq 0 ] && [ "$TOTAL_DB" -gt 0 ]; then
    docker exec "$PG_CONTAINER" psql -U odoo -d odoo -v ON_ERROR_STOP=1 -c \
      "update ir_config_parameter set value='$DAY', write_date=now() where key='saas.last_backup_date'; insert into ir_config_parameter (key,value,create_date,write_date) select 'saas.last_backup_date','$DAY',now(),now() where not exists (select 1 from ir_config_parameter where key='saas.last_backup_date');" \
      >/dev/null
    log "Backup date updated: $DAY"
else
    log "Backup date not updated because verification failed"
fi

log "=== Done: db=$TOTAL_DB filestore=$TOTAL_FS failed=$FAIL size=$(du -sh "$DAY_DIR" | cut -f1) ==="
test "$FAIL" -eq 0
