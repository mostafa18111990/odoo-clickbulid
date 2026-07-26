#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${SAAS_ODOO_CONTAINER:-odoo_saas_app}"
DATABASE="${SAAS_PLATFORM_DB:-odoo}"
LOCK_FILE="${SAAS_DEMO_MAINTENANCE_LOCK:-/run/lock/saas-demo-maintenance.lock}"

exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

test "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" = "true"

timeout 280 docker exec -i "$CONTAINER" \
    odoo shell -c /etc/odoo/odoo.conf -d "$DATABASE" --no-http <<'PY'
Demo = env['saas.demo.request'].sudo()
Demo.cron_demo_maintenance()
env.cr.commit()
print('SaaS demo maintenance completed')
PY
