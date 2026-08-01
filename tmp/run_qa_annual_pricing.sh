#!/usr/bin/env bash
set -Eeuo pipefail
ROOT='/opt/clickbuild-staging/redesign-platform-content'
PATHS="$(sed -n 's/^addons_path[[:space:]]*=[[:space:]]*//p' "$ROOT/config/odoo.conf" | head -1)"
docker run --rm -i --network clickbuild_redesign_net --env-file "$ROOT/.env" \
  -v '/opt/odoo-saas/oca:/mnt/oca:ro' -v '/opt/odoo-saas/cybrosys:/mnt/cybrosys:ro' \
  -v '/opt/odoo-saas/addons:/mnt/extra-addons:ro' -v "$ROOT/runtime-addons:/mnt/stage-addons:ro" \
  -v clickbuild3_stage_odoodata:/var/lib/odoo -v "$ROOT/config/odoo.conf:/etc/odoo/odoo.conf:ro" \
  clickbuild/odoo-community:19 odoo shell -c /etc/odoo/odoo.conf --addons-path="$PATHS" \
  -d clickbuild3_stage --no-http --max-cron-threads=0 < /root/qa_annual_pricing.py
