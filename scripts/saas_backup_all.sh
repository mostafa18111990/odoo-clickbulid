#!/bin/bash
# ClickBuild SaaS — daily backup of master + all tenant databases.
# Designed to run from /etc/cron.daily/saas-backup (via systemd timer).
#
# Per database, produces:
#   /opt/backups/<date>/<db>.dump  (pg_dump custom format, restorable via pg_restore)
#
# Retention: keeps the last N days (default 7), deletes older directories.
# Logs to /var/log/saas-backup.log
#
# Master DB (odoo) is always included. Tenant DBs are discovered from the
# saas.tenant table so newly provisioned tenants are picked up automatically.
set -euo pipefail

BACKUP_ROOT=/opt/backups
DATE=$(date +%Y-%m-%d)
LOG=/var/log/saas-backup.log
RETENTION_DAYS=${SAAS_BACKUP_RETENTION_DAYS:-7}
PG_CONTAINER=odoo_saas_postgres
PG_USER=odoo
MASTER_DB=odoo

mkdir -p "$BACKUP_ROOT/$DATE"

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

log "=== SaaS backup starting (retention $RETENTION_DAYS days) ==="

dump_db() {
    local db="$1"
    local out="$BACKUP_ROOT/$DATE/$db.dump"
    log "dumping $db -> $out"
    if docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -Fc "$db" > "$out" 2>>"$LOG"; then
        local size=$(stat -c%s "$out" 2>/dev/null || echo 0)
        log "  done $db ($(numfmt --to=iec --suffix=B "$size" 2>/dev/null || echo "$size bytes"))"
    else
        log "  FAILED $db"
        rm -f "$out"
        return 1
    fi
}

# 1) Always back up the master DB
dump_db "$MASTER_DB" || log "WARN: master backup failed"

# 2) Discover tenant databases from saas.tenant (excludes archived / cancelled)
log "discovering tenant DBs..."
TENANT_DBS=$(docker exec odoo_saas_app python3 -c "
import odoo
from odoo.tools import config
config.parse_config(['-c', '/etc/odoo/odoo.conf'])
reg = odoo.modules.registry.Registry('odoo')
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    ts = env['saas.tenant'].sudo().search([
        ('state', 'not in', ['cancelled', 'archived', 'deleted']),
        ('api_instance_id', '!=', False)])
    print('\n'.join(t.api_instance_id for t in ts
                    if t.api_instance_id and not t.api_instance_id.startswith('pending:')))
" 2>/dev/null)

# Sanity check: only dump DBs that actually exist
EXISTING_DBS=$(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -lAt | cut -d'|' -f1)

for db in $TENANT_DBS; do
    if echo "$EXISTING_DBS" | grep -qx "$db"; then
        dump_db "$db" || true
    else
        log "WARN: tenant DB $db listed in saas.tenant but does not exist on Postgres — skipping"
    fi
done

# 3) Apply retention — delete directories older than $RETENTION_DAYS
log "applying retention ($RETENTION_DAYS days)..."
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -print -exec rm -rf {} + \
    2>>"$LOG" | sed 's/^/  pruned: /' | tee -a "$LOG"

TOTAL_SIZE=$(du -sh "$BACKUP_ROOT/$DATE" 2>/dev/null | cut -f1)
DB_COUNT=$(ls -1 "$BACKUP_ROOT/$DATE"/*.dump 2>/dev/null | wc -l)
log "=== SaaS backup finished: $DB_COUNT dumps, total $TOTAL_SIZE ==="
