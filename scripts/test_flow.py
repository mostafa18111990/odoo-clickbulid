#!/usr/bin/env python
"""Test the full auth flow via HTTP"""
import urllib.request
import urllib.error
import json
import sys
import time

BASE = "http://129.121.98.243"
API  = f"{BASE}/api/v1"

def req(method, path, data=None, token=None):
    url = f"{API}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as ex:
        return 0, str(ex)

print("=== Testing OdooClickBuild ===\n")

# 1. Health check
status, data = req("GET", "/health")
print(f"[1] Health: {status} -> {data}")

# 2. Frontend pages
import urllib.request as ur
for path in ['/', '/login', '/register', '/verify']:
    try:
        with ur.urlopen(f"{BASE}{path}", timeout=10) as r:
            print(f"[2] {path}: HTTP {r.status} ({'OK' if r.status in [200,307,308] else 'FAIL'})")
    except urllib.error.HTTPError as e:
        print(f"[2] {path}: HTTP {e.code}")
    except Exception as ex:
        print(f"[2] {path}: ERROR {ex}")

# 3. Register
import random, string
suffix = ''.join(random.choices(string.digits, k=4))
test_email = f"test{suffix}@test.com"
status, data = req("POST", "/auth/register", {
    "email": test_email, "password": "TestPass1", "name": "Test User",
    "country": "EG", "language": "ar"
})
print(f"\n[3] Register {test_email}: {status} -> {data}")

if status == 201:
    # 4. Get verification code from DB
    print("\n[4] Checking verification code in DB...")

print("\n=== Done ===")
print(f"\nSite: http://129.121.98.243")
print(f"Register: http://129.121.98.243/register")
print(f"Login:    http://129.121.98.243/login")
print(f"API docs: http://129.121.98.243/api/docs")
