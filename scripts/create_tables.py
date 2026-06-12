#!/usr/bin/env python
"""Create all DB tables and seed default plans"""
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

# Write a one-shot Python script to run on the server
init_script = r'''
import sys
sys.path.insert(0, '/opt/clickbuild/backend')

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.db.base import Base
from app.core.config import settings

# Import all models so they're registered
from app.models import user, instance, subscription, payment

async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("TABLES_CREATED")

    # Seed plans
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from app.models.subscription import Plan
    from sqlalchemy import select

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Plan))
        existing = result.scalars().all()
        if not existing:
            plans = [
                Plan(name="trial",      display_name="تجريبي",    price_monthly=0,    price_yearly=0,    max_users=3,  storage_gb=2,  is_trial=True,  trial_days=14),
                Plan(name="starter",    display_name="مبتدئ",     price_monthly=199,  price_yearly=1990, max_users=5,  storage_gb=10, is_trial=False, trial_days=0),
                Plan(name="business",   display_name="أعمال",     price_monthly=499,  price_yearly=4990, max_users=25, storage_gb=50, is_trial=False, trial_days=0),
                Plan(name="enterprise", display_name="مؤسسي",     price_monthly=999,  price_yearly=9990, max_users=100,storage_gb=200,is_trial=False, trial_days=0),
            ]
            db.add_all(plans)
            await db.commit()
            print("PLANS_SEEDED")
        else:
            print(f"Plans already exist: {[p.name for p in existing]}")

asyncio.run(main())
'''

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(init_script.encode('utf-8')), '/tmp/init_db.py')
sftp.close()

cmd = "cd /opt/clickbuild/backend && source venv/bin/activate && python /tmp/init_db.py 2>&1 | tail -20"
stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(out)
if err.strip():
    print("STDERR:", err[:500])

client.close()
print("Done!")
