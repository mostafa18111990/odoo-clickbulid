#!/usr/bin/env python
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

# Run a quick test script directly in Python to get the actual error
test_script = r'''
import asyncio, sys, traceback
sys.path.insert(0, '/opt/clickbuild/backend')

from app.core.database import AsyncSessionLocal, async_engine
from app.models import user, instance, subscription
from app.models.user import User, UserLanguage, UserCountry
from app.core.security import hash_password, generate_verification_code
from sqlalchemy import select

async def test_register():
    try:
        async with AsyncSessionLocal() as db:
            existing = await db.execute(select(User).where(User.email == 'dbtest@test.com'))
            u = existing.scalar_one_or_none()
            if u:
                print(f"User exists: {u.id}")
                return
            code = generate_verification_code()
            user_obj = User(
                email='dbtest@test.com',
                password_hash=hash_password('TestPass1'),
                name='Test User',
                country=UserCountry.EG,
                language=UserLanguage.AR,
                verification_code=code,
                is_verified=False,
            )
            db.add(user_obj)
            await db.commit()
            await db.refresh(user_obj)
            print(f"SUCCESS: user_id={user_obj.id}, code={code}")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

asyncio.run(test_register())
'''

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(test_script.encode()), '/tmp/test_reg.py')
sftp.close()

cmd = "cd /opt/clickbuild/backend && source venv/bin/activate && python /tmp/test_reg.py 2>&1"
stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
print(stdout.read().decode('utf-8', errors='replace'))

# Also check the FastAPI error output more thoroughly
cmd2 = """cd /opt/clickbuild/backend && source venv/bin/activate && \
python -c "
import uvicorn, asyncio
from app.main import app
" 2>&1"""
stdin, stdout, stderr = client.exec_command(cmd2, timeout=10)
print("Import check:", stdout.read().decode('utf-8', errors='replace'))

# Check what error FastAPI returns
cmd3 = "curl -v http://127.0.0.1:8000/api/v1/auth/register -X POST -H 'Content-Type: application/json' -d '{\"email\":\"dbtest2@test.com\",\"password\":\"TestPass1\",\"name\":\"Test\",\"country\":\"EG\",\"language\":\"ar\"}' 2>&1"
stdin, stdout, stderr = client.exec_command(cmd3, timeout=10)
print("cURL verbose:", stdout.read().decode('utf-8', errors='replace'))

client.close()
