#!/bin/bash
# Weekly regression: clone the community template, run the 29-scenario
# business-cycle harness, report to Telegram, drop the canary DB.
# Exits non-zero on any failure so systemd records the unit as failed.
set -uo pipefail
source /root/.saas-alert.env
CANARY="qa_canary_$(date +%Y%m%d)"
LOG=/var/log/saas-weekly-regression.log
HARNESS_LOG=/var/log/saas-weekly-regression-harness.log
RC=0
echo "$(date -Is) starting regression on $CANARY" >> "$LOG"

cleanup() {
  docker exec odoo_saas_postgres dropdb -U odoo --force --if-exists "$CANARY" >>"$LOG" 2>&1
  docker exec odoo_saas_app rm -rf "/var/lib/odoo/filestore/$CANARY" >>"$LOG" 2>&1
}

cleanup
if ! docker exec odoo_saas_postgres createdb -U odoo -T tpl_community_core -O odoo_community "$CANARY" 2>>"$LOG"; then
  MSG="🔴 الاختبار الأسبوعي: فشل إنشاء قاعدة canary من tpl_community_core — راجع $LOG"
  RC=2
else
  RESULT=$(docker exec -i odoo_saas_app odoo shell -c /etc/odoo/odoo.conf -d "$CANARY" --no-http \
             < /root/harness_core.py 2>"$HARNESS_LOG" | sed -n '/===HARNESS_JSON===/,$p' | tail -1)
  echo "$RESULT" > /root/regression_last.json
  SUMMARY=$(python3 - <<'PYEOF'
import json, sys
try:
    r = json.load(open('/root/regression_last.json'))
    sc = r['scenarios']
    if not sc:
        raise ValueError("no scenarios in harness output")
except Exception as e:
    print("ERROR harness output unparsable:", e)
    sys.exit(3)
p = sum(1 for v in sc.values() if v['status'] == 'PASS')
fails = [k for k, v in sc.items() if v['status'] != 'PASS']
line = f"{p}/{len(sc)} passed"
if fails:
    print(line + " | FAILED: " + ", ".join(fails[:6]))
    sys.exit(1)
print(line)
PYEOF
)
  PRC=$?
  if [ "$PRC" -eq 0 ]; then
    MSG="✅ اختبار الانحدار الأسبوعي: $SUMMARY — دورة الأعمال الكاملة سليمة."
  else
    MSG="🔴 اختبار الانحدار الأسبوعي — يوجد فشل!
$SUMMARY
Details: /root/regression_last.json , $HARNESS_LOG"
    RC=$PRC
  fi
  cleanup
fi
echo "$(date -Is) rc=$RC $MSG" >> "$LOG"
curl -sm 20 "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
     --data-urlencode "chat_id=${TG_CHAT_ID}" --data-urlencode "text=$MSG" >/dev/null \
  || echo "$(date -Is) WARN telegram send failed" >> "$LOG"
exit "$RC"
