#!/usr/bin/env python
"""Seed plans with correct columns"""
import paramiko
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "129.121.98.243"
USER = "root"
PASS = "Mh@01007121878"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

init_script = r'''
import asyncio, sys
sys.path.insert(0, '/opt/clickbuild/backend')

async def main():
    from app.core.database import AsyncSessionLocal, async_engine
    from app.models.subscription import Plan, PlanName
    from sqlalchemy import select, text

    # Show existing tables
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
        tables = [r[0] for r in result]
        print("Tables:", tables)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Plan))
        existing = result.scalars().all()
        if not existing:
            plans = [
                Plan(
                    name=PlanName.TRIAL,
                    name_ar="تجريبي 14 يوم",
                    name_en="14-day Trial",
                    price_egp=0, price_sar=0, price_aed=0, price_usd=0,
                    max_users=3, storage_gb=2.0, max_instances=1,
                    cpu_limit=0.5, memory_mb=512,
                    features_ar=["إنشاء تلقائي فوري","3 مستخدمين","2 جيجا تخزين","وصول كامل لـ 14 يوم"],
                    features_en=["Instant provisioning","3 users","2GB storage","Full access for 14 days"],
                    is_active=True,
                ),
                Plan(
                    name=PlanName.STARTER,
                    name_ar="مبتدئ",
                    name_en="Starter",
                    price_egp=199, price_sar=25, price_aed=25, price_usd=7,
                    max_users=5, storage_gb=10.0, max_instances=1,
                    cpu_limit=1.0, memory_mb=1024,
                    features_ar=["5 مستخدمين","10 جيجا تخزين","CRM + مبيعات + فواتير + مخازن","دعم بالبريد"],
                    features_en=["5 users","10GB storage","CRM + Sales + Invoicing + Inventory","Email support"],
                    is_active=True,
                ),
                Plan(
                    name=PlanName.BUSINESS,
                    name_ar="أعمال",
                    name_en="Business",
                    price_egp=499, price_sar=60, price_aed=60, price_usd=17,
                    max_users=25, storage_gb=50.0, max_instances=3,
                    cpu_limit=2.0, memory_mb=2048,
                    features_ar=["25 مستخدم","50 جيجا تخزين","جميع الوحدات","دعم أولوية"],
                    features_en=["25 users","50GB storage","All modules","Priority support"],
                    is_active=True,
                ),
                Plan(
                    name=PlanName.ENTERPRISE,
                    name_ar="مؤسسي",
                    name_en="Enterprise",
                    price_egp=999, price_sar=120, price_aed=120, price_usd=35,
                    max_users=100, storage_gb=200.0, max_instances=10,
                    cpu_limit=4.0, memory_mb=4096,
                    features_ar=["100 مستخدم","200 جيجا تخزين","جميع الوحدات","دعم مخصص 24/7"],
                    features_en=["100 users","200GB storage","All modules","Dedicated 24/7 support"],
                    is_active=True,
                ),
            ]
            db.add_all(plans)
            await db.commit()
            print("PLANS_SEEDED - 4 plans created")
        else:
            print(f"Plans already exist: {[p.name for p in existing]}")

asyncio.run(main())
'''

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(init_script.encode('utf-8')), '/tmp/seed_plans.py')
sftp.close()

cmd = "cd /opt/clickbuild/backend && source venv/bin/activate && python /tmp/seed_plans.py 2>&1"
stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
out = stdout.read().decode('utf-8', errors='replace')
print(out)

client.close()
print("Done!")
