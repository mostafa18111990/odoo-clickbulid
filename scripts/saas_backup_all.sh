#!/usr/bin/env bash
# Atomic, verified backup of the Odoo 19 control plane and Odoo 19/20 tenants.
set -eEuo pipefail
umask 077

BACKUP_ROOT=${BACKUP_ROOT:-/opt/backups}
DATE=$(date +%Y-%m-%d)
STAMP=$(date +%Y-%m-%d-%H%M%S)
RETENTION_DAYS=${SAAS_BACKUP_RETENTION_DAYS:-7}
VALIDATE_ONLY=${SAAS_BACKUP_VALIDATE_ONLY:-0}
SKIP_OFFSITE=${SAAS_BACKUP_SKIP_OFFSITE:-0}
PG19=${MASTER_PG_CONTAINER:-odoo_saas_postgres}
PG20=${ODOO20_PG_CONTAINER:-odoo_saas_postgres20}
PG_USER=${PG_USER:-odoo}
MASTER_DB=${MASTER_DB:-odoo}
LOG=${SAAS_BACKUP_LOG:-/var/log/saas-backup.log}
LOCK=${SAAS_BACKUP_LOCK:-/run/lock/saas-backup.lock}
WORK="$BACKUP_ROOT/.daily-$STAMP-$$"
FINAL="$BACKUP_ROOT/$DATE"
PREVIOUS="$BACKUP_ROOT/.previous-$DATE-$$"
ODOO19_COMMUNITY_VOLUME=${ODOO19_COMMUNITY_VOLUME:-odoo-saas_odoo_data}
ODOO19_ENTERPRISE_VOLUME=${ODOO19_ENTERPRISE_VOLUME:-odoo-saas_odoo_ent_data}
ODOO20_COMMUNITY_VOLUME=${ODOO20_COMMUNITY_VOLUME:-clickbuild-odoo20-tenants_odoo20-community-data}
ODOO20_ENTERPRISE_VOLUME=${ODOO20_ENTERPRISE_VOLUME:-clickbuild-odoo20-tenants_odoo20-enterprise-data}

exec 9>"$LOCK"
flock -n 9 || {
    echo "$(date -Is) another backup is already running" >&2
    exit 75
}

cleanup() {
    [[ "$WORK" == "$BACKUP_ROOT"/.daily-* ]] || return 1
    rm -rf -- "$WORK"
}
trap cleanup EXIT
log() { printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

db_exists() {
    local container="$1" db="$2"
    docker inspect "$container" >/dev/null 2>&1 &&
        docker exec "$container" psql -U "$PG_USER" -d postgres -Atc \
            "select 1 from pg_database where datname='$db'" 2>/dev/null | grep -qx 1
}

dump_verified() {
    local container="$1"
    local db="$2"
    local output="$WORK/databases/$db.dump"
    log "dumping database=$db plane=$container"
    docker exec "$container" pg_dump -U "$PG_USER" -Fc "$db" >"$output"
    test -s "$output"
    docker exec -i "$container" pg_restore --list <"$output" >/dev/null
}

archive_filestore() {
    local volume="$1" output_name="$2" root
    root=$(docker volume inspect "$volume" -f '{{.Mountpoint}}')
    test -d "$root/filestore"
    log "archiving filestore volume=$volume"
    tar -C "$root" -czf "$WORK/$output_name" filestore
    test -s "$WORK/$output_name"
    tar -tzf "$WORK/$output_name" >/dev/null
}

log "full Odoo 19/20 backup starting retention_days=$RETENTION_DAYS"

mapfile -t tenant_dbs < <(
    docker exec "$PG19" psql -U "$PG_USER" -d "$MASTER_DB" -Atc \
        "select distinct api_instance_id
           from saas_tenant
          where state not in ('cancelled','archived','deleted')
            and api_instance_id is not null
            and api_instance_id not like 'pending:%'
          order by api_instance_id"
)

if [[ "$VALIDATE_ONLY" == "1" ]]; then
    odoo19_count=1
    odoo20_count=0
    for db in "${tenant_dbs[@]}"; do
        [[ "$db" =~ ^[A-Za-z0-9_-]+$ ]] || exit 21
        if db_exists "$PG20" "$db"; then
            odoo20_count=$((odoo20_count + 1))
        elif db_exists "$PG19" "$db"; then
            odoo19_count=$((odoo19_count + 1))
        else
            log "FAILED tracked database is unavailable on both PostgreSQL planes: $db"
            exit 22
        fi
    done
    for volume in \
        "$ODOO19_COMMUNITY_VOLUME" "$ODOO19_ENTERPRISE_VOLUME" \
        "$ODOO20_COMMUNITY_VOLUME" "$ODOO20_ENTERPRISE_VOLUME"; do
        root=$(docker volume inspect "$volume" -f '{{.Mountpoint}}')
        test -d "$root/filestore"
    done
    echo "BACKUP_VALIDATION_OK odoo19=$odoo19_count odoo20=$odoo20_count"
    exit 0
fi

install -d -m 700 "$WORK/databases"
dump_verified "$PG19" "$MASTER_DB"
odoo19_count=1
odoo20_count=0
for db in "${tenant_dbs[@]}"; do
    [[ "$db" =~ ^[A-Za-z0-9_-]+$ ]] || {
        log "FAILED invalid database identifier"
        exit 21
    }
    if db_exists "$PG20" "$db"; then
        dump_verified "$PG20" "$db"
        odoo20_count=$((odoo20_count + 1))
    elif db_exists "$PG19" "$db"; then
        dump_verified "$PG19" "$db"
        odoo19_count=$((odoo19_count + 1))
    else
        log "FAILED tracked database is unavailable on both PostgreSQL planes: $db"
        exit 22
    fi
done

archive_filestore "$ODOO19_COMMUNITY_VOLUME" community-filestore.tar.gz
archive_filestore "$ODOO19_ENTERPRISE_VOLUME" enterprise-filestore.tar.gz
archive_filestore "$ODOO20_COMMUNITY_VOLUME" odoo20-community-filestore.tar.gz
archive_filestore "$ODOO20_ENTERPRISE_VOLUME" odoo20-enterprise-filestore.tar.gz

config_list="$WORK/platform-config-files.list"
if ! odoo20_release=$(readlink -f /opt/odoo20-releases/current 2>/dev/null); then
    log 'FAILED current Odoo 20 release could not be resolved'
    exit 23
fi
if [[ "$odoo20_release" != /opt/odoo20-releases/* ]]; then
    log 'FAILED resolved Odoo 20 release is outside the releases root'
    exit 23
fi
for path in \
    /opt/odoo-saas/addons \
    /opt/odoo-saas/config \
    /opt/odoo-saas/docker \
    /opt/odoo-saas/docker-community-external \
    /opt/odoo-saas/docker-enterprise \
    /opt/odoo-saas/nginx-tenants \
    /opt/odoo-saas/scripts \
    /opt/odoo-saas/secrets \
    /opt/odoo-saas/enterprise20 \
    /opt/odoo-saas/docker-compose.yml \
    /opt/odoo20-staging/repo/docker/odoo20/.env \
    "$odoo20_release" \
    /etc/systemd/system \
    /etc/letsencrypt \
    /usr/local/bin/saas-backup-all.sh \
    /usr/local/bin/saas-sync-tenant-metrics.sh \
    /usr/local/bin/saas-tenant-provisioner.sh \
    /usr/local/bin/saas-warm-pool.sh \
    /usr/local/bin/saas-demo-maintenance.sh; do
    [[ -e "$path" ]] && printf '%s\n' "${path#/}" >>"$config_list"
done
tar -C / -czf "$WORK/platform-config-and-addons.tar.gz" -T "$config_list"

for archive in "$WORK"/*.tar.gz; do
    test -s "$archive"
    tar -tzf "$archive" >/dev/null
done

cat >"$WORK/MANIFEST.txt" <<EOF
created_at=$STAMP
odoo19_database_count=$odoo19_count
odoo20_database_count=$odoo20_count
includes_odoo19_community_filestore=yes
includes_odoo19_enterprise_filestore=yes
includes_odoo20_community_filestore=yes
includes_odoo20_enterprise_filestore=yes
includes_platform_config_and_addons=yes
includes_deployed_odoo20_release=yes
retention_days=$RETENTION_DAYS
EOF

(
    cd "$WORK"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
    sha256sum -c SHA256SUMS >/dev/null
)

if [[ -d "$FINAL" ]]; then
    mv -- "$FINAL" "$PREVIOUS"
fi
mv -- "$WORK" "$FINAL"
trap - EXIT
rm -rf -- "$PREVIOUS"
chmod -R go-rwx "$FINAL"

# Delete date-named daily backups only; pre-deployment snapshots are preserved.
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
    -regextype posix-extended \
    -regex "$BACKUP_ROOT/[0-9]{4}-[0-9]{2}-[0-9]{2}" \
    -mtime "+$RETENTION_DAYS" -print -exec rm -rf -- {} + \
    | sed 's/^/pruned_daily=/' | tee -a "$LOG"

if [[ "$SKIP_OFFSITE" != "1" ]] && mountpoint -q /mnt/odoo-backups-offsite; then
    install -d -m 700 "/mnt/odoo-backups-offsite/$DATE"
    rsync -a --delete "$FINAL/" "/mnt/odoo-backups-offsite/$DATE/"
    log "offsite copy completed"
elif [[ "$SKIP_OFFSITE" != "1" ]]; then
    log "WARN offsite mount not configured; local verified copy retained"
fi

size=$(du -sh "$FINAL" | awk '{print $1}')
total_count=$((odoo19_count + odoo20_count))
log "full daily backup finished databases=$total_count odoo19=$odoo19_count odoo20=$odoo20_count size=$size"
echo "BACKUP_OK path=$FINAL databases=$total_count odoo20=$odoo20_count size=$size"
