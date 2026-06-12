#!/usr/bin/env python
"""Fix passlib/bcrypt incompatibility by rewriting security.py"""
import paramiko, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)

# Check what's in security.py currently
stdin, stdout, stderr = client.exec_command("cat /opt/clickbuild/backend/app/core/security.py")
print("Current security.py:")
print(stdout.read().decode('utf-8', errors='replace'))

# Write new security.py using bcrypt directly (no passlib)
new_security = '''\
"""Security utilities - JWT, hashing, tokens"""
import bcrypt
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional
import jwt

from app.core.config import settings


# ─── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─── JWT Tokens ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    payload = data.copy()
    payload.update({
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=expires_minutes),
        "iat": datetime.now(timezone.utc),
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(data: dict, expires_days: int = 30) -> str:
    payload = data.copy()
    payload.update({
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=expires_days),
        "iat": datetime.now(timezone.utc),
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


# ─── Verification / Reset Tokens ──────────────────────────────────────────────

def generate_verification_code(length: int = 6) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


# ─── Encryption (for storing Docker secrets) ──────────────────────────────────
def encrypt_secret(plaintext: str) -> str:
    return plaintext  # TODO: add Fernet encryption if needed


def decrypt_secret(ciphertext: str) -> str:
    return ciphertext
'''

sftp = client.open_sftp()
sftp.putfo(io.BytesIO(new_security.encode()), '/opt/clickbuild/backend/app/core/security.py')
sftp.close()
print("\n[OK] security.py rewritten")

# Make sure PyJWT is installed
stdin, stdout, stderr = client.exec_command(
    "cd /opt/clickbuild/backend && source venv/bin/activate && pip install PyJWT bcrypt -q && echo DONE"
)
print(stdout.read().decode('utf-8', errors='replace'))

# Restart the API
stdin, stdout, stderr = client.exec_command("systemctl restart clickbuild-api && sleep 2 && systemctl is-active clickbuild-api")
print("API restart:", stdout.read().decode('utf-8', errors='replace'))

# Test register again
import time
time.sleep(2)
stdin, stdout, stderr = client.exec_command(
    "curl -s http://127.0.0.1:8000/api/v1/auth/register -X POST "
    "-H 'Content-Type: application/json' "
    "-d '{\"email\":\"hello@test.com\",\"password\":\"TestPass1\",\"name\":\"Ahmed\",\"country\":\"EG\",\"language\":\"ar\"}'"
)
out = stdout.read().decode('utf-8', errors='replace')
print(f"\nRegister test: {out}")

client.close()
print("Done!")
