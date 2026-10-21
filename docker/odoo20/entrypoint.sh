#!/bin/bash
# ClickBuild Odoo Entrypoint
# يقوم بتوليد odoo.conf من المتغيرات ثم تشغيل Odoo

set -e

# ─── توليد Config من Template ────────────────────────────────────────────────
envsubst < /etc/odoo/odoo.conf.template > /etc/odoo/odoo.conf

# ─── انتظار PostgreSQL ────────────────────────────────────────────────────────
echo "⏳ انتظار قاعدة البيانات..."
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" > /dev/null 2>&1; do
    sleep 1
done
echo "✅ قاعدة البيانات جاهزة"

# ─── تهيئة قاعدة البيانات عند أول تشغيل ─────────────────────────────────────
if [ "${INIT_DB:-false}" = "true" ]; then
    echo "🚀 تهيئة قاعدة البيانات الجديدة: ${DB_NAME}"
    odoo --config=/etc/odoo/odoo.conf \
        --database="${DB_NAME}" \
        --init="${ODOO_MODULES:-base,web}" \
        --without-demo="${WITHOUT_DEMO:-all}" \
        --load-language="${ODOO_LANG:-ar_001,en_US}" \
        --stop-after-init

    # إنشاء Admin User
    python3 << PYEOF
import psycopg2, os, hashlib, secrets

conn = psycopg2.connect(
    host=os.environ['DB_HOST'],
    dbname=os.environ['DB_NAME'],
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD']
)
cur = conn.cursor()

admin_email = os.environ.get('ADMIN_EMAIL', 'admin@clickbuild.com')
admin_pass  = os.environ.get('ADMIN_PASSWORD', secrets.token_urlsafe(12))

# تحديث بيانات admin
cur.execute("""
    UPDATE res_users SET login=%s WHERE id=2
""", (admin_email,))

cur.execute("""
    UPDATE res_partner SET email=%s, name=%s WHERE id IN (
        SELECT partner_id FROM res_users WHERE id=2
    )
""", (admin_email, os.environ.get('COMPANY_NAME', 'My Company')))

conn.commit()
cur.close()
conn.close()

print(f"✅ Admin Email: {admin_email}")
PYEOF

    echo "✅ تم تهيئة قاعدة البيانات"
fi

# ─── تشغيل Odoo ──────────────────────────────────────────────────────────────
echo "🚀 بدء تشغيل Odoo ${ODOO_VERSION:-19}..."
exec odoo --config=/etc/odoo/odoo.conf "$@"
