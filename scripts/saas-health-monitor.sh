#!/bin/bash
# ClickBuild platform health monitor.
# Secrets are loaded from ALERT_ENV and are never written to the log.
set -uo pipefail

ALERT_ENV="${ALERT_ENV:-/root/.saas-alert.env}"
STATE_DIR="${STATE_DIR:-/var/lib/saas-monitor}"
LOG="${LOG:-/var/log/saas-health-monitor.log}"
FAILURE_THRESHOLD="${FAILURE_THRESHOLD:-2}"
RECOVERY_THRESHOLD="${RECOVERY_THRESHOLD:-2}"
HTTP_RETRIES="${HTTP_RETRIES:-3}"
HTTP_RETRY_DELAY="${HTTP_RETRY_DELAY:-2}"
DRY_RUN="${DRY_RUN:-0}"
MAIN_URL="${MAIN_URL:-https://odoo.clickbulid.com/}"
SIGNUP_URL="${SIGNUP_URL:-https://odoo.clickbulid.com/get-started}"
TENANT_DOMAIN="${TENANT_DOMAIN:-odoo.clickbulid.com}"
CHECK_TENANTS="${CHECK_TENANTS:-1}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-odoo_saas_postgres}"
CENTRAL_DB="${CENTRAL_DB:-odoo}"
CONTAINERS="${CONTAINERS:-odoo_saas_app odoo_saas_ent odoo_saas_nginx odoo_saas_postgres}"
TLS_SERVER_NAME="${TLS_SERVER_NAME:-odoo.clickbulid.com}"

# shellcheck source=/dev/null
source "$ALERT_ENV"
mkdir -p "$STATE_DIR"
umask 077

exec 9>"$STATE_DIR/monitor.lock"
flock -n 9 || exit 0

FAILS=""
log() { echo "$(date -Is) $1" >> "$LOG"; }
add_failure() { FAILS="${FAILS}$1; "; }

http_ok() {
  local name="$1" url="$2" attempt code rc
  for ((attempt = 1; attempt <= HTTP_RETRIES; attempt++)); do
    code=$(curl --silent --show-error --location \
      --connect-timeout 5 --max-time 12 \
      --output /dev/null --write-out '%{http_code}' "$url" 2>>"$LOG")
    rc=$?
    if [ "$rc" -eq 0 ] && [[ "$code" =~ ^2[0-9][0-9]$ ]]; then
      return 0
    fi
    log "HTTP retry name=$name attempt=$attempt rc=$rc status=${code:-000}"
    [ "$attempt" -lt "$HTTP_RETRIES" ] && sleep "$HTTP_RETRY_DELAY"
  done
  return 1
}

http_ok main-site "$MAIN_URL" || add_failure main-site
http_ok signup-page "$SIGNUP_URL" || add_failure signup-page

if [ "$CHECK_TENANTS" = "1" ]; then
  TENANTS=$(docker exec "$POSTGRES_CONTAINER" psql -U odoo -d "$CENTRAL_DB" -Atc \
    "SELECT subdomain FROM saas_tenant WHERE state IN ('active','trial') AND create_date < now() - interval '15 minutes' ORDER BY id LIMIT 20" \
    2>>"$LOG") || TENANTS=""
  for tenant in $TENANTS; do
    http_ok "tenant-$tenant" "https://${tenant}.${TENANT_DOMAIN}/web/login" || add_failure "tenant-$tenant"
  done
fi

for container in $CONTAINERS; do
  [ "$(docker inspect --format '{{.State.Running}}' "$container" 2>/dev/null)" = "true" ] || \
    add_failure "container-$container"
done

docker exec "$POSTGRES_CONTAINER" pg_isready -U odoo >/dev/null 2>&1 || add_failure postgres

DB_CAPACITY=$(docker exec "$POSTGRES_CONTAINER" psql -U odoo -d postgres -Atc \
  "SELECT count(*)::text || ':' || current_setting('max_connections') FROM pg_stat_activity" \
  2>>"$LOG") || DB_CAPACITY=""
if [[ "$DB_CAPACITY" =~ ^([0-9]+):([0-9]+)$ ]]; then
  DB_USED="${BASH_REMATCH[1]}"
  DB_MAX="${BASH_REMATCH[2]}"
  if [ $((DB_USED * 100 / DB_MAX)) -ge 85 ]; then
    log "PostgreSQL connection capacity high used=$DB_USED max=$DB_MAX"
    add_failure postgres-connections-high
  fi
else
  add_failure postgres-capacity-check
fi

DISK_USE=$(df / --output=pcent | tail -1 | tr -dc '0-9')
[ "${DISK_USE:-0}" -lt 90 ] || add_failure "disk-${DISK_USE}pct"

CERT_END=$(echo | openssl s_client -connect localhost:443 -servername "$TLS_SERVER_NAME" 2>/dev/null | \
  openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
if [ -n "$CERT_END" ]; then
  END_TS=$(date -d "$CERT_END" +%s 2>/dev/null || echo 0)
  DAYS_LEFT=$(((END_TS - $(date +%s)) / 86400))
  [ "$DAYS_LEFT" -ge 14 ] || add_failure "cert-expires-${DAYS_LEFT}d"
else
  add_failure cert-check-failed
fi

NEWEST=$(find /opt/backups -mindepth 1 -maxdepth 1 -type d -name '20*' -printf '%T@ %p\n' 2>/dev/null | \
  sort -n | tail -1 | cut -d' ' -f2-)
if [ -n "$NEWEST" ]; then
  AGE_H=$((($(date +%s) - $(stat -c %Y "$NEWEST")) / 3600))
  [ "$AGE_H" -le 26 ] || add_failure "backup-stale-${AGE_H}h"
else
  add_failure backup-missing
fi

send_mail() {
  local subject="$1" body="$2" mail_file
  mail_file=$(mktemp "$STATE_DIR/mail.XXXXXX") || return 1
  {
    echo "From: ClickBuild Monitor <${SMTP_USER}>"
    echo "To: ${ALERT_TO}"
    echo "Subject: ${subject}"
    echo
    echo "$body"
  } > "$mail_file"
  curl --silent --max-time 30 --url "$SMTP_URL" \
    --user "${SMTP_USER}:${SMTP_PASS}" --mail-from "$SMTP_USER" \
    --mail-rcpt "$ALERT_TO" -T "$mail_file" >/dev/null 2>&1
  local rc=$?
  rm -f "$mail_file"
  return "$rc"
}

send_telegram() {
  [ -n "${TG_TOKEN:-}" ] && [ -n "${TG_CHAT_ID:-}" ] || return 1
  curl --silent --max-time 20 "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TG_CHAT_ID}" --data-urlencode "text=$1" >/dev/null 2>&1
}

notify() {
  local subject="$1" body="$2" ok=1
  if [ "$DRY_RUN" = "1" ]; then
    log "DRY RUN notification subject=$subject"
    return 0
  fi
  send_telegram "$subject
$body" && ok=0
  send_mail "$subject" "$body" && ok=0
  return "$ok"
}

read_state() { [ -f "$1" ] && cat "$1" || :; }
PREV=$(read_state "$STATE_DIR/failing")
CANDIDATE=$(read_state "$STATE_DIR/failure_candidate")
FAIL_COUNT=$(read_state "$STATE_DIR/failure_count")
RECOVERY_COUNT=$(read_state "$STATE_DIR/recovery_count")
FAIL_COUNT="${FAIL_COUNT:-0}"
RECOVERY_COUNT="${RECOVERY_COUNT:-0}"

if [ -n "$FAILS" ]; then
  rm -f "$STATE_DIR/recovery_count"
  if [ "$FAILS" = "$CANDIDATE" ]; then
    FAIL_COUNT=$((FAIL_COUNT + 1))
  else
    CANDIDATE="$FAILS"
    FAIL_COUNT=1
  fi
  printf '%s' "$CANDIDATE" > "$STATE_DIR/failure_candidate"
  printf '%s' "$FAIL_COUNT" > "$STATE_DIR/failure_count"
  log "FAIL candidate=$FAIL_COUNT/$FAILURE_THRESHOLD checks=$FAILS"

  if [ "$FAIL_COUNT" -ge "$FAILURE_THRESHOLD" ]; then
    LAST_ALERT=$(read_state "$STATE_DIR/last_alert")
    LAST_ALERT="${LAST_ALERT:-0}"
    NOW=$(date +%s)
    if [ "$FAILS" != "$PREV" ] || [ $((NOW - LAST_ALERT)) -gt 3600 ]; then
      if notify "[ALERT] ClickBuild platform problem" "Failing checks: ${FAILS}
Server: srv1809722 (72.60.46.204)
Time: $(date -Is)"; then
        printf '%s' "$NOW" > "$STATE_DIR/last_alert"
      else
        log "alert delivery failed on all channels"
      fi
    fi
    printf '%s' "$FAILS" > "$STATE_DIR/failing"
  fi
else
  rm -f "$STATE_DIR/failure_candidate" "$STATE_DIR/failure_count"
  if [ -n "$PREV" ]; then
    RECOVERY_COUNT=$((RECOVERY_COUNT + 1))
    printf '%s' "$RECOVERY_COUNT" > "$STATE_DIR/recovery_count"
    log "RECOVERY candidate=$RECOVERY_COUNT/$RECOVERY_THRESHOLD previous=$PREV"
    if [ "$RECOVERY_COUNT" -ge "$RECOVERY_THRESHOLD" ]; then
      notify "[OK] ClickBuild platform recovered" "All checks passing again.
Previously failing: ${PREV}
Time: $(date -Is)" || log "recovery notification failed"
      rm -f "$STATE_DIR/failing" "$STATE_DIR/last_alert" "$STATE_DIR/recovery_count"
    fi
  fi
fi
