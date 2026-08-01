#!/usr/bin/env bash
set -Eeuo pipefail
bash /root/run_qa_annual_pricing.sh
bash /root/run_qa_crm_bridge.sh
echo RECENT_STAGE_ERRORS
docker logs --since 15m clickbuild3_stage_web 2>&1 | grep -E 'ERROR|CRITICAL|Traceback' | tail -20 || true
echo LATEST_BACKUP
ls -lh /opt/clickbuild-staging/backups/pre-phase1-accessibility-2026-08-01-203821/clickbuild3_stage.dump
cat /opt/clickbuild-staging/backups/pre-phase1-accessibility-2026-08-01-203821/SHA256SUMS
echo SAFETY
docker exec clickbuild_redesign_db psql -U odoo -d clickbuild3_stage -AtF '|' -c \
  "select 'active_crons',count(*) from ir_cron where active union all select 'active_mail',count(*) from ir_mail_server where active union all select 'enabled_payments',count(*) from payment_provider where state='enabled';"
