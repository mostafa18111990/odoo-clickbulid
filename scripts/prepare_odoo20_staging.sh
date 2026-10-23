#!/usr/bin/env bash
# Prepare an isolated PostgreSQL 16 staging copy of one non-active Enterprise
# tenant. This script does not stop, restart, or modify production containers.
set -euo pipefail
umask 077

PROD_PG_CONTAINER="${PROD_PG_CONTAINER:-odoo_saas_postgres}"
PROD_ODOO_CONTAINER="${PROD_ODOO_CONTAINER:-odoo_saas_ent}"
MASTER_DB="${MASTER_DB:-odoo}"
STAGE_ROOT="${STAGE_ROOT:-/opt/odoo20-staging}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/backups/pre-odoo20-staging}"
STAGE_PG_CONTAINER="${STAGE_PG_CONTAINER:-odoo20_staging_pg16}"
STAGE_NETWORK="${STAGE_NETWORK:-odoo20-staging-net}"
STAGE_PG_VOLUME="${STAGE_PG_VOLUME:-odoo20_staging_pgdata}"
STAGE_FILESTORE_VOLUME="${STAGE_FILESTORE_VOLUME:-odoo20_staging_filestore}"
TARGET_DB="${TARGET_DB:-stage_enterprise20_probe}"
PG_IMAGE="${PG_IMAGE:-postgres:16-alpine}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$BACKUP_ROOT/$TS"

log() { printf '[odoo20-staging] %s\n' "$*"; }
fail() { printf '[odoo20-staging] ERROR: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null || fail "docker is required"
docker inspect "$PROD_PG_CONTAINER" >/dev/null 2>&1 || fail "production PostgreSQL container not found"
docker inspect "$PROD_ODOO_CONTAINER" >/dev/null 2>&1 || fail "Enterprise Odoo container not found"
docker inspect "$STAGE_PG_CONTAINER" >/dev/null 2>&1 && fail "staging PostgreSQL container already exists"
[[ "$TARGET_DB" =~ ^[A-Za-z0-9_]+$ ]] || fail "unsafe target database name"

SOURCE_DB="$({
  docker exec "$PROD_PG_CONTAINER" psql -U odoo -d "$MASTER_DB" -Atqc \
    "select t.subdomain
       from saas_tenant t
      where t.edition = 'enterprise'
        and t.state = 'suspended'
        and t.subdomain ~ '^[A-Za-z0-9_-]+$'
        and exists (select 1 from pg_database d where d.datname = t.subdomain)
      order by t.id
      limit 1"
} | tr -d '\r')"
[[ "$SOURCE_DB" =~ ^[A-Za-z0-9_-]+$ ]] || fail "no safe suspended Enterprise database is available"

mkdir -p "$BACKUP_DIR" "$STAGE_ROOT"
chmod 700 "$BACKUP_DIR" "$STAGE_ROOT"

log "creating a verified pre-staging database backup"
docker exec "$PROD_PG_CONTAINER" pg_dump -U odoo -Fc -d "$SOURCE_DB" >"$BACKUP_DIR/source.dump"
test -s "$BACKUP_DIR/source.dump" || fail "database dump is empty"
docker exec -i "$PROD_PG_CONTAINER" pg_restore --list <"$BACKUP_DIR/source.dump" >/dev/null

log "backing up the matching filestore when present"
if docker exec "$PROD_ODOO_CONTAINER" test -d "/var/lib/odoo/filestore/$SOURCE_DB"; then
  docker exec "$PROD_ODOO_CONTAINER" tar -czf - -C /var/lib/odoo/filestore "$SOURCE_DB" \
    >"$BACKUP_DIR/filestore.tar.gz"
  test -s "$BACKUP_DIR/filestore.tar.gz" || fail "filestore archive is empty"
  tar -tzf "$BACKUP_DIR/filestore.tar.gz" >/dev/null
else
  log "source database has no filestore directory"
fi

log "archiving deployed addon code"
tar -C /opt/odoo-saas -czf "$BACKUP_DIR/deployed-addons.tar.gz" addons
tar -tzf "$BACKUP_DIR/deployed-addons.tar.gz" >/dev/null

log "recording runtime configuration checksums"
find /opt/odoo-saas -maxdepth 3 -type f \
  \( -name 'docker-compose*.yml' -o -name 'docker-compose*.yaml' -o -name '*.conf' \) \
  -print0 | sort -z | xargs -0 -r sha256sum >"$BACKUP_DIR/runtime-config.sha256"
test -s "$BACKUP_DIR/runtime-config.sha256" || fail "no runtime configuration checksums were produced"
sha256sum "$BACKUP_DIR/source.dump" "$BACKUP_DIR/deployed-addons.tar.gz" \
  >"$BACKUP_DIR/artifacts.sha256"
if test -f "$BACKUP_DIR/filestore.tar.gz"; then
  sha256sum "$BACKUP_DIR/filestore.tar.gz" >>"$BACKUP_DIR/artifacts.sha256"
fi
sha256sum -c "$BACKUP_DIR/artifacts.sha256" >/dev/null

log "starting an isolated PostgreSQL 16 container"
STAGE_PG_PASSWORD="$(openssl rand -hex 32)"
printf 'POSTGRES_USER=odoo\nPOSTGRES_PASSWORD=%s\nTARGET_DB=%s\n' \
  "$STAGE_PG_PASSWORD" "$TARGET_DB" >"$STAGE_ROOT/staging.env"
chmod 600 "$STAGE_ROOT/staging.env"

docker network inspect "$STAGE_NETWORK" >/dev/null 2>&1 || docker network create "$STAGE_NETWORK" >/dev/null
docker volume inspect "$STAGE_PG_VOLUME" >/dev/null 2>&1 || docker volume create "$STAGE_PG_VOLUME" >/dev/null
docker volume inspect "$STAGE_FILESTORE_VOLUME" >/dev/null 2>&1 || docker volume create "$STAGE_FILESTORE_VOLUME" >/dev/null

docker run -d \
  --name "$STAGE_PG_CONTAINER" \
  --network "$STAGE_NETWORK" \
  --env-file "$STAGE_ROOT/staging.env" \
  -e POSTGRES_DB=postgres \
  -v "$STAGE_PG_VOLUME:/var/lib/postgresql/data" \
  --health-cmd='pg_isready -U odoo -d postgres' \
  --health-interval=5s \
  --health-timeout=5s \
  --health-retries=24 \
  "$PG_IMAGE" >/dev/null

for _ in $(seq 1 36); do
  STATUS="$(docker inspect "$STAGE_PG_CONTAINER" --format '{{.State.Health.Status}}')"
  test "$STATUS" = healthy && break
  test "$STATUS" = unhealthy && fail "staging PostgreSQL became unhealthy"
  sleep 5
done
test "$(docker inspect "$STAGE_PG_CONTAINER" --format '{{.State.Health.Status}}')" = healthy \
  || fail "staging PostgreSQL did not become healthy"

log "restoring the database into PostgreSQL 16"
docker exec "$STAGE_PG_CONTAINER" createdb -U odoo -O odoo "$TARGET_DB"
docker exec -i "$STAGE_PG_CONTAINER" pg_restore -U odoo -d "$TARGET_DB" --no-owner --no-acl \
  <"$BACKUP_DIR/source.dump"

if test -f "$BACKUP_DIR/filestore.tar.gz"; then
  docker run --rm \
    -v "$STAGE_FILESTORE_VOLUME:/dest" \
    -v "$BACKUP_DIR:/backup:ro" \
    "$PG_IMAGE" sh -ec \
      "mkdir -p '/dest/$TARGET_DB'; tar -xzf /backup/filestore.tar.gz -C '/dest/$TARGET_DB' --strip-components=1; chown -R 101:101 '/dest/$TARGET_DB'"
fi

log "verifying the restored copy"
SOURCE_TABLES="$(docker exec "$PROD_PG_CONTAINER" psql -U odoo -d "$SOURCE_DB" -Atqc \
  "select count(1) from information_schema.tables where table_schema='public'")"
TARGET_TABLES="$(docker exec "$STAGE_PG_CONTAINER" psql -U odoo -d "$TARGET_DB" -Atqc \
  "select count(1) from information_schema.tables where table_schema='public'")"
SOURCE_MODULES="$(docker exec "$PROD_PG_CONTAINER" psql -U odoo -d "$SOURCE_DB" -Atqc \
  "select count(1) from ir_module_module where state='installed'")"
TARGET_MODULES="$(docker exec "$STAGE_PG_CONTAINER" psql -U odoo -d "$TARGET_DB" -Atqc \
  "select count(1) from ir_module_module where state='installed'")"

test "$SOURCE_TABLES" = "$TARGET_TABLES" || fail "table count differs after restore"
test "$SOURCE_MODULES" = "$TARGET_MODULES" || fail "installed module count differs after restore"
docker exec "$STAGE_PG_CONTAINER" psql -U odoo -d "$TARGET_DB" -v ON_ERROR_STOP=1 -Atqc \
  "select count(1) from res_users" >/dev/null

cat >"$STAGE_ROOT/restore-verification.txt" <<EOF
verified_at_utc=$TS
postgres_image=$PG_IMAGE
target_database=$TARGET_DB
public_tables=$TARGET_TABLES
installed_modules=$TARGET_MODULES
backup_directory=$BACKUP_DIR
EOF
chmod 600 "$STAGE_ROOT/restore-verification.txt"

log "staging restore verified: PostgreSQL 16, tables=$TARGET_TABLES, installed_modules=$TARGET_MODULES"
log "production containers were not restarted or modified"
