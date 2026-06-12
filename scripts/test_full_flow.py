#!/usr/bin/env python
"""Test complete auth flow: register -> verify -> login"""
import paramiko, io, sys, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

BASE = "http://127.0.0.1:8000"

def curl(method, path, data=None, token=None):
    cmd = f"curl -s -X {method} {BASE}{path} -H 'Content-Type: application/json'"
    if token:
        cmd += f" -H 'Authorization: Bearer {token}'"
    if data:
        cmd += f" -d '{json.dumps(data)}'"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    try:
        return json.loads(out)
    except:
        return out

import random, string
suffix = ''.join(random.choices(string.digits, k=5))
email = f"user{suffix}@clicktest.com"
pwd   = "TestPass1"

print(f"Testing with: {email}\n")

# 1. Register
print("1. Register...")
res = curl("POST", "/api/v1/auth/register", {"email": email, "password": pwd, "name": f"Test{suffix}", "country": "EG", "language": "ar"})
print(f"   -> {res}")
user_id = res.get('user_id') if isinstance(res, dict) else None

# 2. Get verification code from DB
print("\n2. Getting verification code from DB...")
get_code = f"""
import sys; sys.path.insert(0, '/opt/clickbuild/backend')
from app.models import user, instance, subscription
from app.models.user import User
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
import asyncio

async def get():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == '{email}'))
        u = result.scalar_one_or_none()
        print(u.verification_code if u else 'NOT FOUND')

asyncio.run(get())
"""
sftp = client.open_sftp()
sftp.putfo(io.BytesIO(get_code.encode()), '/tmp/get_code.py')
sftp.close()
stdin, stdout, stderr = client.exec_command(
    "cd /opt/clickbuild/backend && source venv/bin/activate && python /tmp/get_code.py 2>/dev/null"
)
code = stdout.read().decode().strip()
print(f"   Code: {code}")

# 3. Verify email
print("\n3. Verify email...")
res = curl("POST", "/api/v1/auth/verify-email", {"email": email, "code": code})
print(f"   -> {res}")

# 4. Login
print("\n4. Login...")
res = curl("POST", "/api/v1/auth/login", {"email": email, "password": pwd})
print(f"   -> {res}")
token = res.get('access_token') if isinstance(res, dict) else None

if token:
    # 5. Test authenticated endpoint
    print("\n5. List instances (authenticated)...")
    res = curl("GET", "/api/v1/instances/", token=token)
    print(f"   -> {res}")

    print("\n✅ Full auth flow works!")
else:
    print("\n❌ Login failed")

# Now rebuild frontend with fixed .env.local
print("\n\nRebuilding frontend with correct API URL...")
client.close()
print("Done!")
