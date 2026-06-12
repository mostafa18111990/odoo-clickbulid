#!/usr/bin/env python
"""Final verification - all pages and API"""
import urllib.request, urllib.error, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "http://129.121.98.243"
API  = f"{BASE}/api/v1"

def get(url, token=None):
    try:
        headers = {}
        if token: headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.url
    except urllib.error.HTTPError as e:
        return e.code, url
    except Exception as ex:
        return 0, str(ex)

print("=" * 50)
print("OdooClickBuild - Final Status Check")
print("=" * 50)

pages = ['/ar', '/ar/login', '/ar/register', '/ar/verify', '/ar/dashboard', '/ar/create']
print("\n[Pages]")
for page in pages:
    status, final_url = get(f"{BASE}{page}")
    icon = "OK" if status in [200, 307, 308] else "FAIL"
    print(f"  [{icon}] {page} -> HTTP {status}")

print("\n[API]")
try:
    with urllib.request.urlopen(f"{BASE}/api/health", timeout=5) as r:
        body = json.loads(r.read())
        print(f"  [OK] /api/health -> {body}")
except Exception as ex:
    print(f"  [FAIL] /api/health -> {ex}")

try:
    data = json.dumps({"email":"check@t.com","password":"TestPass1"}).encode()
    req = urllib.request.Request(f"{API}/auth/login", data=data, headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        print(f"  [OK] POST /auth/login -> HTTP {r.status}")
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    print(f"  [OK] POST /auth/login -> HTTP {e.code} ({body.get('detail',{}).get('ar','') or body.get('detail','')})")

print(f"\nSite:     {BASE}")
print(f"API Docs: {BASE}/api/docs")
print(f"Register: {BASE}/ar/register")
print(f"Login:    {BASE}/ar/login")
print("=" * 50)
