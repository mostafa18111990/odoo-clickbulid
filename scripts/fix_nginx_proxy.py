#!/usr/bin/env python
"""Fix Nginx: separate main domain from instance subdomains + add proxy router"""
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
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out + err

# ── 1. Updated nginx main config ─────────────────────────────────────────────
print("[1/4] Updating nginx config...")
upload('/etc/nginx/sites-available/clickbuild-platform', f"""
# ════════════════════════════════════════════
# MAIN PLATFORM - {DOMAIN}
# ════════════════════════════════════════════
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

    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header Strict-Transport-Security "max-age=31536000" always;
}}

# ════════════════════════════════════════════
# ODOO INSTANCES - *.{DOMAIN}
# HTTP redirect to HTTPS
# ════════════════════════════════════════════
server {{
    listen 80;
    server_name ~^(?P<sub>[^.]+)\\.{DOMAIN}$;
    location /.well-known/acme-challenge/ {{ root /var/www/html; }}
    location / {{ return 301 https://$host$request_uri; }}
}}

# HTTPS catch-all for instances (uses main cert, cert warning until wildcard added)
# Per-instance configs in sites-available/instances/ will override this
server {{
    listen 443 ssl;
    server_name ~^(?P<sub>[^.]+)\\.{DOMAIN}$;

    ssl_certificate     {CERT};
    ssl_certificate_key {KEY};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    proxy_read_timeout  720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout  720s;
    client_max_body_size 512m;

    # Route via FastAPI proxy (resolves subdomain -> Odoo port)
    location / {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_set_header   X-Odoo-Subdomain $sub;
    }}

    location /longpolling {{
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Odoo-Subdomain $sub;
    }}
}}
""")

# ── 2. Proxy router for FastAPI ───────────────────────────────────────────────
print("[2/4] Creating proxy router...")
upload('/opt/clickbuild/backend/app/api/v1/endpoints/proxy.py', '''"""
Subdomain proxy - forwards *.odoo.clickbulid.com requests to correct Odoo container
Reads X-Odoo-Subdomain header set by nginx, looks up the port, proxies the request.
"""
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, Response
from fastapi.routing import APIRouter
from sqlalchemy import select
import httpx, asyncio

from app.core.database import get_db
from app.models.instance import Instance, InstanceStatus

router = APIRouter(tags=["subdomain-proxy"])

# Cache subdomain -> port to avoid DB hit on every request
_port_cache: dict = {}
_cache_ttl  = 60  # seconds
_cache_time: dict = {}


async def _resolve_port(subdomain: str) -> int:
    import time
    now = time.time()
    if subdomain in _port_cache and (now - _cache_time.get(subdomain, 0)) < _cache_ttl:
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
    raise HTTPException(503, f"Instance '{subdomain}' not available")


@router.api_route(
    "/{path:path}",
    methods=["GET","POST","PUT","DELETE","PATCH","HEAD","OPTIONS"],
    include_in_schema=False
)
async def subdomain_proxy(path: str, request: Request):
    subdomain = request.headers.get("X-Odoo-Subdomain")
    if not subdomain:
        return Response(status_code=404)

    try:
        port = await _resolve_port(subdomain)
    except HTTPException:
        return Response(
            content=f"<h1>Instance not available</h1><p>{subdomain} is not running.</p>",
            status_code=503,
            media_type="text/html"
        )

    qs     = f"?{request.url.query}" if request.url.query else ""
    target = f"http://127.0.0.1:{port}/{path}{qs}"
    body   = await request.body()

    # Filter headers
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in {"host", "connection", "transfer-encoding", "te", "trailers", "upgrade"}
    }
    headers["host"] = request.headers.get("host", f"{subdomain}.odoo.clickbulid.com")

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
            if k.lower() not in {"transfer-encoding", "connection"}
        }
        return Response(
            content     = resp.content,
            status_code = resp.status_code,
            headers     = resp_headers,
            media_type  = resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        return Response(
            content=f"<h1>Connection failed</h1><p>Cannot reach Odoo on port {port}</p>",
            status_code=502, media_type="text/html"
        )
''')

# ── 3. Update main.py ─────────────────────────────────────────────────────────
print("[3/4] Updating main.py...")
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

app.include_router(auth.router,      prefix="/api/v1")
app.include_router(instances.router, prefix="/api/v1")
app.include_router(payments.router,  prefix="/api/v1")
app.include_router(admin.router,     prefix="/api/v1")
app.include_router(proxy.router)     # catch-all - must be last


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
''')

# ── 4. Install httpx + reload nginx + restart API ────────────────────────────
print("[4/4] Installing httpx + reloading services...")
cmds = [
    "cd /opt/clickbuild/backend && source venv/bin/activate && pip install httpx -q && echo HTTPX_OK",
    "nginx -t 2>&1",
    "systemctl reload nginx && echo NGINX_RELOADED",
    "systemctl restart clickbuild-api && sleep 4 && curl -s http://127.0.0.1:8000/api/health",
    "curl -sk -o /dev/null -w '%{http_code}' https://odoo.clickbulid.com/api/health",
]
for cmd in cmds:
    out = run(cmd, timeout=60)
    print(f"  > {out.strip()[:200]}")

sftp.close()
client.close()
print("\nDone! Nginx now correctly routes:")
print(f"  https://{DOMAIN}     -> FastAPI + Next.js")
print(f"  https://sub.{DOMAIN} -> Odoo container (via proxy)")
