#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

STAMP="$(date +%Y-%m-%d-%H%M%S)"
ROOT='/opt/clickbuild-staging/redesign-platform-content'
ADDONS="$ROOT/addons"
RUNTIME="$ROOT/runtime-addons"
BACKUP="/opt/clickbuild-staging/backups/pre-phase1-seo-$STAMP"
DB_CONTAINER='clickbuild_redesign_db'; DB='clickbuild3_stage'; WEB='clickbuild3_stage_web'
NETWORK='clickbuild_redesign_net'; VOLUME='clickbuild3_stage_odoodata'; PORT='18079'
IMAGE='clickbuild/odoo-community:19'
ADDONS_PATH="$(sed -n 's/^addons_path[[:space:]]*=[[:space:]]*//p' "$ROOT/config/odoo.conf" | head -1)"

test -s /root/clickbuild-phase1-seo.tar.gz
test -n "$ADDONS_PATH"
mkdir -p "$BACKUP"
docker exec "$DB_CONTAINER" pg_dump -U odoo -Fc -d "$DB" >"$BACKUP/$DB.dump"
docker exec -i "$DB_CONTAINER" pg_restore --list <"$BACKUP/$DB.dump" >"$BACKUP/$DB.dump.list"
cp -a "$RUNTIME" "$BACKUP/runtime-addons"
if [ -d "$ADDONS/clickbuild_seo" ]; then
  cp -a "$ADDONS/clickbuild_seo" "$BACKUP/clickbuild_seo"
fi

start_stage() {
  docker run -d --name "$WEB" --restart unless-stopped --network "$NETWORK" \
    --env-file "$ROOT/.env" -p "127.0.0.1:$PORT:8069" \
    -v '/opt/odoo-saas/oca:/mnt/oca:ro' -v '/opt/odoo-saas/cybrosys:/mnt/cybrosys:ro' \
    -v '/opt/odoo-saas/addons:/mnt/extra-addons:ro' -v "$RUNTIME:/mnt/stage-addons:ro" \
    -v "$VOLUME:/var/lib/odoo" -v "$ROOT/config/odoo.conf:/etc/odoo/odoo.conf:ro" \
    "$IMAGE" odoo -c /etc/odoo/odoo.conf --addons-path="$ADDONS_PATH" -d "$DB" \
    "--db-filter=^$DB$" --max-cron-threads=0 >/dev/null
}

rollback() {
  trap - ERR INT TERM
  docker rm -f clickbuild3_stage_upgrade "$WEB" >/dev/null 2>&1 || true
  rm -rf "$ADDONS/clickbuild_seo" "$RUNTIME"
  if [ -d "$BACKUP/clickbuild_seo" ]; then
    cp -a "$BACKUP/clickbuild_seo" "$ADDONS/clickbuild_seo"
  fi
  cp -a "$BACKUP/runtime-addons" "$RUNTIME"
  docker exec "$DB_CONTAINER" psql -U odoo -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB' AND pid <> pg_backend_pid();" >/dev/null
  docker exec "$DB_CONTAINER" dropdb -U odoo --if-exists "$DB"
  docker exec "$DB_CONTAINER" createdb -U odoo "$DB"
  docker exec -i "$DB_CONTAINER" pg_restore -U odoo -d "$DB" --no-owner --no-privileges \
    <"$BACKUP/$DB.dump" >/dev/null
  start_stage
}

on_error(){ local rc="$1" line="$2" cmd="$3"; echo "FAILED rc=$rc line=$line cmd=$cmd" >&2; rollback; exit "$rc"; }
trap 'on_error "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap 'on_error 130 "$LINENO" interrupted' INT TERM

tar -xzf /root/clickbuild-phase1-seo.tar.gz -C "$ADDONS"
for module in saas_website saas_demo_management clickbuild_content clickbuild_website_core clickbuild_crm_bridge clickbuild_seo; do
  test -s "$ADDONS/$module/__manifest__.py"
done
rm -rf "$RUNTIME"; mkdir -p "$RUNTIME"
for module in saas_website saas_demo_management clickbuild_content clickbuild_website_core clickbuild_crm_bridge clickbuild_seo; do
  cp -a "$ADDONS/$module" "$RUNTIME/$module"
done
chmod 755 "$RUNTIME"

docker rm -f "$WEB" >/dev/null
docker run --rm --name clickbuild3_stage_upgrade --network "$NETWORK" --env-file "$ROOT/.env" \
  -v '/opt/odoo-saas/oca:/mnt/oca:ro' -v '/opt/odoo-saas/cybrosys:/mnt/cybrosys:ro' \
  -v '/opt/odoo-saas/addons:/mnt/extra-addons:ro' -v "$RUNTIME:/mnt/stage-addons:ro" \
  -v "$VOLUME:/var/lib/odoo" -v "$ROOT/config/odoo.conf:/etc/odoo/odoo.conf:ro" \
  "$IMAGE" odoo -c /etc/odoo/odoo.conf --addons-path="$ADDONS_PATH" -d "$DB" \
  "--db-filter=^$DB$" --stop-after-init --no-http --max-cron-threads=0 \
  -u 'clickbuild_seo'

docker exec "$DB_CONTAINER" psql -U odoo -d "$DB" -v ON_ERROR_STOP=1 -c \
  "update ir_module_module set state='uninstalled' where name in ('contacts_enterprise','crm_enterprise','spreadsheet_dashboard_crm','web_cohort','web_map') and state='to install'; update ir_cron set active=false where active; update ir_mail_server set active=false where active; update payment_provider set state='disabled' where state='enabled'; delete from ir_attachment where url like '/sitemap-%';" >/dev/null
start_stage

probe(){ local code=000; for _ in $(seq 1 90); do code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 "$1" || true)"; [ "$code" = "$2" ] && break; sleep 2; done; echo "$3|$code"; test "$code" = "$2"; }
probe https://staging.odoo.clickbulid.com/ 200 staging_home
probe https://staging.odoo.clickbulid.com/en 200 staging_en
probe https://staging.odoo.clickbulid.com/robots.txt 200 staging_robots
probe https://staging.odoo.clickbulid.com/sitemap.xml 200 staging_sitemap
probe https://staging.odoo.clickbulid.com/web/database/manager 404 staging_db_manager
probe https://odoo.clickbulid.com/ 200 production_home

curl -fsS https://staging.odoo.clickbulid.com/robots.txt > /tmp/clickbuild-robots.txt
curl -fsS https://staging.odoo.clickbulid.com/sitemap.xml > /tmp/clickbuild-sitemap.xml
grep -qx 'Disallow: /' /tmp/clickbuild-robots.txt
! grep -q 'http://staging.odoo.clickbulid.com' /tmp/clickbuild-sitemap.xml
for excluded in '/contactus' '/help' '/error' '/get-started/success' '/website/info'; do
  ! grep -q "<loc>[^<]*${excluded}</loc>" /tmp/clickbuild-sitemap.xml
done
for required in '/apps' '/industries' '/pricing' '/about' '/contact'; do
  grep -q "https://staging.odoo.clickbulid.com${required}" /tmp/clickbuild-sitemap.xml
done

test "$(docker exec "$DB_CONTAINER" psql -U odoo -d "$DB" -Atc "select count(*) from ir_module_module where name='clickbuild_seo' and state='installed'")" = 1
docker exec "$DB_CONTAINER" psql -U odoo -d "$DB" -Atc \
  "select 'active_crons='||count(*) from ir_cron where active; select 'active_mail='||count(*) from ir_mail_server where active; select 'enabled_payments='||count(*) from payment_provider where state='enabled';"
test "$(docker exec "$DB_CONTAINER" psql -U odoo -d "$DB" -Atc "select count(*) from ir_cron where active")" = 0
test "$(docker exec "$DB_CONTAINER" psql -U odoo -d "$DB" -Atc "select count(*) from ir_mail_server where active")" = 0
test "$(docker exec "$DB_CONTAINER" psql -U odoo -d "$DB" -Atc "select count(*) from payment_provider where state='enabled'")" = 0
sha256sum "$BACKUP/$DB.dump" >"$BACKUP/SHA256SUMS"
trap - ERR INT TERM
echo PHASE1_SEO_STAGING=PASS
echo "ROLLBACK_PATH=$BACKUP"
