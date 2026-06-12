#!/usr/bin/env python
"""Create DB tables and seed plans on the server"""
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
    from app.core.database import async_engine, Base, AsyncSessionLocal
    from app.models import user, instance, subscription

    # Create all tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("TABLES_OK")

    # Seed plans
    from sqlalchemy import select, text
    from app.models.subscription import Plan, PlanName

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Plan))
        existing = result.scalars().all()
        if not existing:
            plans = [
                Plan(name=PlanName.TRIAL,      display_name="تجريبي 14 يوم",  price_monthly=0,    price_yearly=0,    max_users=3,   storage_gb=2,   is_trial=True,  trial_days=14,  features={"modules": ["crm","sales","invoicing"]}),
                Plan(name=PlanName.STARTER,    display_name="مبتدئ",           price_monthly=199,  price_yearly=1990, max_users=5,   storage_gb=10,  is_trial=False, trial_days=0,   features={"modules": ["crm","sales","invoicing","inventory"]}),
                Plan(name=PlanName.BUSINESS,   display_name="أعمال",           price_monthly=499,  price_yearly=4990, max_users=25,  storage_gb=50,  is_trial=False, trial_days=0,   features={"modules": ["all"]}),
                Plan(name=PlanName.ENTERPRISE, display_name="مؤسسي",           price_monthly=999,  price_yearly=9990, max_users=100, storage_gb=200, is_trial=False, trial_days=0,   features={"modules": ["all"], "dedicated": True}),
            ]
            db.add_all(plans)
            await db.commit()
            print("PLANS_SEEDED")
        else:
            print(f"Plans already exist: {[p.name for p in existing]}")

    # List tables
    async with async_engine.connect() as conn:
        result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))
        tables = [r[0] for r in result]
        print("Tables:", tables)

asyncio.run(main())
'''

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(init_script.encode('utf-8')), '/tmp/init_db.py')
sftp.close()

cmd = "cd /opt/clickbuild/backend && source venv/bin/activate && python /tmp/init_db.py 2>&1"
stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
out = stdout.read().decode('utf-8', errors='replace')
print(out)

client.close()
print("Done!")
