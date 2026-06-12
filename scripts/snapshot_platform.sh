#!/bin/bash
# Build a full self-contained snapshot of the ClickBuild SaaS platform.
# Stored under /opt/backups/snapshots/<timestamp>/ and tarred up at the end
# into a single file for easy mirroring/restore.
#
# Contents per snapshot:
#   dbs/*.dump             - pg_dump custom-format for each Postgres DB
#   opt_odoo_saas.tar.gz   - /opt/odoo-saas (config, addons, certs, nginx-tenants, compose)
#   letsencrypt.tar.gz     - /etc/letsencrypt (live certs + renewal config)
#   filestore.tar.gz       - the Odoo filestore docker volume contents
#   systemd/*              - the unit files for sweeper + certbot timer
#   MANIFEST.txt           - timestamp, DB list, tenant list, git hash, sizes
#   restore.sh             - replay everything (database-by-database)
#
# Usage:
#   ./snapshot_platform.sh             # create snapshot
#   ./snapshot_platform.sh --list      # list existing snapshots
set -euo pipefail

ROOT=/opt/backups/snapshots
mkdir -p "$ROOT"

if [ "${1:-}" = "--list" ]; then
    echo "Snapshots in $ROOT:"
    ls -lh "$ROOT"/*.tar.gz 2>/dev/null || echo "  (none yet)"
    exit 0
fi

TS=$(date +%Y%m%d-%H%M%S)
SNAP=$ROOT/$TS
mkdir -p "$SNAP/dbs" "$SNAP/systemd"
echo "[snapshot] building $SNAP"

# ─── 1. Postgres dumps ─────────────────────────────────────────────────────
# List user databases (skip template* and postgres).
DBS=$(docker exec odoo_saas_postgres psql -U odoo -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datistemplate=false AND datname NOT IN ('postgres')")

echo "[snapshot] dumping $(echo "$DBS" | wc -l) databases:"
for db in $DBS; do
    echo "  - $db"
    docker exec odoo_saas_postgres pg_dump -U odoo -Fc -d "$db" > "$SNAP/dbs/${db}.dump"
done

# ─── 2. /opt/odoo-saas (config + addons + nginx-tenants + cert-requests) ──
echo "[snapshot] archiving /opt/odoo-saas..."
tar -C /opt -czf "$SNAP/opt_odoo_saas.tar.gz" \
    --exclude='odoo-saas/logs' \
    --exclude='odoo-saas/filestore' \
    --exclude='odoo-saas/*.bak.*' \
    --exclude='odoo-saas/config/nginx.conf.bak.*' \
    odoo-saas

# ─── 3. Let's Encrypt ──────────────────────────────────────────────────────
echo "[snapshot] archiving /etc/letsencrypt..."
tar -czf "$SNAP/letsencrypt.tar.gz" -C /etc letsencrypt

# ─── 4. Odoo filestore (docker volume) ─────────────────────────────────────
FILESTORE_PATH=$(docker volume inspect odoo-saas_odoo_data --format '{{.Mountpoint}}' 2>/dev/null || echo "")
if [ -n "$FILESTORE_PATH" ] && [ -d "$FILESTORE_PATH" ]; then
    echo "[snapshot] archiving filestore volume ($FILESTORE_PATH)..."
    tar -czf "$SNAP/filestore.tar.gz" -C "$(dirname $FILESTORE_PATH)" "$(basename $FILESTORE_PATH)"
else
    echo "[snapshot] WARN: filestore volume not found, skipping"
fi

# ─── 5. systemd units (sweeper + certbot) ──────────────────────────────────
for unit in saas-cert-sweeper.service saas-cert-sweeper.timer; do
    [ -f /etc/systemd/system/$unit ] && cp /etc/systemd/system/$unit "$SNAP/systemd/"
done
cp /usr/local/bin/saas-cert-sweeper.sh "$SNAP/systemd/" 2>/dev/null || true
cp /usr/local/bin/saas-tenant-provisioner.sh "$SNAP/systemd/" 2>/dev/null || true

# ─── 6. MANIFEST ────────────────────────────────────────────────────────────
{
    echo "ClickBuild SaaS Platform Snapshot"
    echo "  Timestamp:  $TS"
    echo "  Server:     $(hostname) ($(hostname -I | awk '{print $1}'))"
    echo "  Odoo image: $(docker inspect odoo_saas_app --format '{{.Config.Image}}' 2>/dev/null)"
    echo "  Postgres:   $(docker inspect odoo_saas_postgres --format '{{.Config.Image}}' 2>/dev/null)"
    echo "  Nginx:      $(docker inspect odoo_saas_nginx --format '{{.Config.Image}}' 2>/dev/null)"
    echo
    echo "Databases dumped:"
    for f in "$SNAP/dbs/"*.dump; do
        printf "  %-30s %s\n" "$(basename $f .dump)" "$(du -h $f | cut -f1)"
    done
    echo
    echo "Component sizes:"
    du -h "$SNAP"/*.tar.gz 2>/dev/null
    echo
    echo "Active tenants (from master DB):"
    docker exec odoo_saas_app python3 -c "
import odoo
from odoo.tools import config
config.parse_config(['-c', '/etc/odoo/odoo.conf'])
reg = odoo.modules.registry.Registry('odoo')
with reg.cursor() as cr:
    env = odoo.api.Environment(cr, 1, {})
    for t in env['saas.tenant'].with_context(active_test=False).search([]):
        print(f'  {t.id:3d}  {t.subdomain:20s}  state={t.state:10s}  db={t.api_instance_id or \"-\"}')
" 2>&1 | grep -vE 'WARNING|tools.config|modules.loading' | tail -30
} > "$SNAP/MANIFEST.txt"

# ─── 7. restore.sh — replay snapshot ───────────────────────────────────────
cat > "$SNAP/restore.sh" << 'RESTORE'
#!/bin/bash
# Replay this snapshot back onto the server.
# DESTRUCTIVE — drops/recreates every database listed in dbs/.
# Run from inside the snapshot directory.
set -euo pipefail

if [ "${1:-}" != "--yes-i-understand" ]; then
    cat <<'EOF'
This will REPLACE the live platform with the snapshot:
  - Stop docker containers
  - Drop and re-create every database in dbs/
  - Restore /opt/odoo-saas and /etc/letsencrypt
  - Restore the Odoo filestore
  - Reinstall systemd units
  - Bring everything back up

Run again with:    ./restore.sh --yes-i-understand
EOF
    exit 2
fi

cd "$(dirname "$0")"
echo "[restore] stopping containers..."
cd /opt/odoo-saas && docker compose stop odoo nginx
cd -

echo "[restore] restoring /opt/odoo-saas..."
rm -rf /opt/odoo-saas.pre-restore.$(date +%s) 2>/dev/null || true
mv /opt/odoo-saas /opt/odoo-saas.pre-restore.$(date +%s)
tar -xzf opt_odoo_saas.tar.gz -C /opt
chown -R root:root /opt/odoo-saas
chmod 0777 /opt/odoo-saas/cert-requests 2>/dev/null || true

echo "[restore] restoring /etc/letsencrypt..."
mv /etc/letsencrypt /etc/letsencrypt.pre-restore.$(date +%s)
tar -xzf letsencrypt.tar.gz -C /etc

echo "[restore] restoring filestore..."
if [ -f filestore.tar.gz ]; then
    docker volume rm odoo-saas_odoo_data 2>/dev/null || true
    docker volume create odoo-saas_odoo_data
    DEST=$(docker volume inspect odoo-saas_odoo_data --format '{{.Mountpoint}}')
    tar -xzf filestore.tar.gz -C "$(dirname $DEST)"
fi

echo "[restore] restoring systemd units..."
cp systemd/*.service /etc/systemd/system/ 2>/dev/null || true
cp systemd/*.timer   /etc/systemd/system/ 2>/dev/null || true
cp systemd/*.sh      /usr/local/bin/      2>/dev/null || true
chmod +x /usr/local/bin/saas-*.sh         2>/dev/null || true
systemctl daemon-reload
systemctl enable --now saas-cert-sweeper.timer 2>/dev/null || true

echo "[restore] starting postgres..."
cd /opt/odoo-saas && docker compose up -d postgres
sleep 5

echo "[restore] restoring databases..."
for f in dbs/*.dump; do
    db=$(basename "$f" .dump)
    echo "  - $db"
    docker exec odoo_saas_postgres psql -U odoo -d postgres -c \
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$db'" >/dev/null 2>&1 || true
    docker exec odoo_saas_postgres dropdb -U odoo --if-exists "$db"
    docker exec odoo_saas_postgres createdb -U odoo -O odoo "$db"
    cat "$f" | docker exec -i odoo_saas_postgres pg_restore -U odoo -d "$db" --no-owner --no-acl --clean --if-exists -j 2 || true
done

echo "[restore] starting odoo + nginx..."
docker compose up -d odoo nginx
sleep 6
docker exec odoo_saas_nginx nginx -s reload

cat <<EOF
[restore] done.
  Sanity checks:
    docker ps
    curl -sS http://127.0.0.1:9181/healthz
    curl -sS https://odoo.clickbulid.com/web/login -I | head -1
EOF
RESTORE
chmod +x "$SNAP/restore.sh"

# ─── 8. Bundle everything into a single tar.gz for easy mirroring ──────────
echo "[snapshot] bundling final tarball..."
tar -C "$ROOT" -czf "$ROOT/clickbuild-snapshot-$TS.tar.gz" "$TS"
TOTAL=$(du -h "$ROOT/clickbuild-snapshot-$TS.tar.gz" | cut -f1)

# Clean staging dir? Keep both for now so you can browse without untarring.
echo
echo "═══════════════════════════════════════════════════════════════"
echo "  ✓ Snapshot complete"
echo "  Bundle: $ROOT/clickbuild-snapshot-$TS.tar.gz  ($TOTAL)"
echo "  Browse: $SNAP/"
echo "═══════════════════════════════════════════════════════════════"
echo
cat "$SNAP/MANIFEST.txt"
