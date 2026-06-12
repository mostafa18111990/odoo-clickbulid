#!/usr/bin/env python
"""Fix proxy routing - use /odoo-proxy/ prefix to avoid catching API routes"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"
CERT   = f"/etc/letsencrypt/live/{DOMAIN}/fullchain.pem"
KEY    = f"/etc/letsencrypt/live/{DOMAIN}/privkey.pem"

def upload(path, content):
    sftp.putfo(io.BytesIO(content.encode('utf-8')), path)
    print(f"  [OK] {path}")

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Fix proxy.py - use /odoo-proxy/ prefix
upload('/opt/clickbuild/backend/app/api/v1/endpoints/proxy.py', '''"""
Subdomain proxy - routes Odoo instance traffic
Nginx subdomain block passes requests to /odoo-proxy/{path} with X-Odoo-Subdomain header
"""
from fastapi import Request, APIRouter
from fastapi.responses import Response
from sqlalchemy import select
import httpx

from app.core.database import get_db
from app.models.instance import Instance, InstanceStatus

router = APIRouter(tags=["subdomain-proxy"])

_port_cache: dict = {}
_cache_time: dict = {}
_CACHE_TTL = 60


async def _resolve_port(subdomain: str) -> int | None:
    import time
    now = time.time()
    if subdomain in _port_cache and (now - _cache_time.get(subdomain, 0)) < _CACHE_TTL:
        return _port_cache[subdomain]
    async for db in get_db():
        result = await db.execute(
            select(Instance).where(
                Instance.subdomain == subdomain,
                Instance.status    == InstanceStatus.RUNNING
            )
        )
        inst = result.scalar_one_or_none()
        if inst and inst.odoo_port:
            _port_cache[subdomain] = inst.odoo_port
            _cache_time[subdomain] = now
            return inst.odoo_port
    return None


@router.api_route(
    "/odoo-proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def subdomain_proxy(path: str, request: Request):
    subdomain = request.headers.get("X-Odoo-Subdomain")
    if not subdomain:
        return Response(status_code=400, content="Missing X-Odoo-Subdomain header")

    port = await _resolve_port(subdomain)
    if not port:
        return Response(
            content=f"<html><body><h1>Instance Unavailable</h1>"
                    f"<p><b>{subdomain}</b> is not running or does not exist.</p></body></html>",
            status_code=503,
            media_type="text/html",
        )

    qs     = f"?{request.url.query}" if request.url.query else ""
    target = f"http://127.0.0.1:{port}/{path}{qs}"
    body   = await request.body()

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "connection", "transfer-encoding", "te", "trailers", "upgrade", "content-length"}
    }
    headers["host"] = f"{subdomain}.{request.headers.get('host', '')}"
    if body:
        headers["content-length"] = str(len(body))

    try:
        async with httpx.AsyncClient(timeout=60.0) as cli:
            resp = await cli.request(
                method           = request.method,
                url              = target,
                headers          = headers,
                content          = body,
                follow_redirects = False,
            )
        resp_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in {"transfer-encoding", "connection", "content-encoding"}
        }
        return Response(
            content     = resp.content,
            status_code = resp.status_code,
            headers     = resp_headers,
        )
    except httpx.ConnectError:
        return Response(
            content=f"<html><body><h2>Cannot connect to Odoo (port {port})</h2></body></html>",
            status_code=502, media_type="text/html",
        )
''')

# 2. Fix main.py - health endpoint BEFORE proxy router
upload('/opt/clickbuild/backend/app/main.py', '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import create_tables
from app.api.v1.endpoints import auth, instances, payments, admin, proxy


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(
    title    = settings.APP_NAME,
    version  = settings.APP_VERSION,
    docs_url = "/api/docs",
    redoc_url= None,
    lifespan = lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = settings.ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# API routes first (specific paths)
app.include_router(auth.router,      prefix="/api/v1")
app.include_router(instances.router, prefix="/api/v1")
app.include_router(payments.router,  prefix="/api/v1")
app.include_router(admin.router,     prefix="/api/v1")
app.include_router(proxy.router)     # /odoo-proxy/* - no conflict with /api/


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
''')

# 3. Fix nginx - subdomain block uses /odoo-proxy/ prefix
upload('/etc/nginx/sites-available/clickbuild-platform', f"""
# ═══════════════════════════════════════════
# MAIN PLATFORM - {DOMAIN}
# ═══════════════════════════════════════════
server {{
    listen 80;
    server_name {DOMAIN} www.{DOMAIN};
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

server {{
    listen 443 ssl;
    server_name {DOMAIN} www.{DOMAIN};

    ssl_certificate     {CERT};
    ssl_certificate_key {KEY};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;
    client_max_body_size 100M;

    location /api/ {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }}

    location / {{
        proxy_pass         http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection 'upgrade';
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}

    add_header Strict-Transport-Security "max-age=31536000" always;
}}

# ═══════════════════════════════════════════
# ODOO INSTANCES - *.{DOMAIN}
# ═══════════════════════════════════════════
server {{
    listen 80;
    server_name ~^(?P<sub>[^.]+)\\.{DOMAIN}$;
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

server {{
    listen 443 ssl;
    server_name ~^(?P<sub>[^.]+)\\.{DOMAIN}$;

    ssl_certificate     {CERT};
    ssl_certificate_key {KEY};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    proxy_read_timeout    720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout    720s;
    client_max_body_size  512m;

    # Route to FastAPI proxy endpoint with subdomain context
    location / {{
        proxy_pass         http://127.0.0.1:8000/odoo-proxy$request_uri;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   X-Odoo-Subdomain $sub;
    }}
}}
""")

# 4. Restart API + reload nginx
print("Restarting services...")
cmds = [
    "nginx -t 2>&1",
    "systemctl reload nginx && echo NGINX_OK",
    "systemctl restart clickbuild-api && sleep 5 && curl -s http://127.0.0.1:8000/api/health",
    "curl -sk https://odoo.clickbulid.com/api/health",
]
for cmd in cmds:
    out = run(cmd, timeout=30)
    print(f"  > {out.strip()[:200]}")

sftp.close()
client.close()
print("\nDone! Routing fixed:")
print(f"  https://{DOMAIN}/api/* -> FastAPI API")
print(f"  https://{DOMAIN}/*     -> Next.js")
print(f"  https://sub.{DOMAIN}/  -> FastAPI /odoo-proxy/* -> Odoo container")
