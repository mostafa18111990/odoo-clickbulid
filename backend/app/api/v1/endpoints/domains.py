"""
Domains Endpoints — Custom domain SSL + Nginx automation (Phase 8).

Called by Odoo's saas_domain_manager SslBridgeService. This is the ONLY
place certbot + Nginx vhost generation runs — never inside Odoo.

Flow for issue_ssl:
  1. Generate HTTP Nginx vhost (so the ACME HTTP-01 challenge can be served)
  2. Run certbot --nginx to obtain + install the cert
  3. Parse cert expiry, return to Odoo

Security: internal bearer token (shared with Odoo).

Routes (mounted under /api/v1):
  POST   /domains/ssl/issue
  POST   /domains/ssl/renew
  DELETE /domains/{domain}
"""
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from typing import Optional
import subprocess
import re
import os
import logging
from datetime import datetime

from app.core.config import settings

_logger = logging.getLogger(__name__)
router = APIRouter(prefix="/domains", tags=["domains"])

NGINX_SITES = "/etc/nginx/sites-available"
NGINX_ENABLED = "/etc/nginx/sites-enabled"
CERT_LIVE = "/etc/letsencrypt/live"
ACME_EMAIL = "admin@clickbuild.com"
DOMAIN_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)(\.[a-z0-9-]{1,63})+$")


# ─── Auth ───────────────────────────────────────────────────────────────────────

def verify_internal_token(authorization: str = Header(None)):
    expected = f"Bearer {settings.INTERNAL_API_TOKEN}"
    if not authorization or authorization != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")
    return True


# ─── Schemas ────────────────────────────────────────────────────────────────────

class SslIssueRequest(BaseModel):
    domain: str
    tenant_subdomain: str
    tenant_port: Optional[int] = None
    saas_domain_id: Optional[int] = None


class SslRenewRequest(BaseModel):
    domain: str


# ─── Issue SSL ──────────────────────────────────────────────────────────────────

@router.post("/ssl/issue")
async def issue_ssl(body: SslIssueRequest, _=Depends(verify_internal_token)):
    """Generate Nginx vhost + obtain Let's Encrypt cert for a custom domain."""
    domain = (body.domain or "").lower().strip()
    if not DOMAIN_RE.match(domain):
        raise HTTPException(400, "Invalid domain")

    # Resolve upstream port for the tenant
    port = body.tenant_port or _lookup_tenant_port(body.tenant_subdomain)
    if not port:
        return {"success": False, "error": "Could not resolve tenant upstream port"}

    try:
        # 1. Write an HTTP-only vhost first (serves ACME challenge + proxies)
        _write_http_vhost(domain, port)
        _reload_nginx()

        # 2. Run certbot (installs cert + rewrites vhost to HTTPS)
        result = subprocess.run(
            [
                "certbot", "--nginx",
                "-d", domain,
                "--non-interactive", "--agree-tos",
                "-m", ACME_EMAIL,
                "--redirect",
            ],
            capture_output=True, timeout=120,
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="ignore")[-400:]
            _logger.error("certbot failed for %s: %s", domain, err)
            return {"success": False, "error": f"certbot: {err}"}

        # 3. Read expiry
        expires_at = _cert_expiry(domain)
        _logger.info("SSL issued for %s, expires %s", domain, expires_at)
        return {"success": True, "expires_at": expires_at}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "SSL issuance timed out"}
    except Exception as e:
        _logger.error("issue_ssl error for %s: %s", domain, e)
        return {"success": False, "error": str(e)}


# ─── Renew SSL ──────────────────────────────────────────────────────────────────

@router.post("/ssl/renew")
async def renew_ssl(body: SslRenewRequest, _=Depends(verify_internal_token)):
    domain = (body.domain or "").lower().strip()
    if not DOMAIN_RE.match(domain):
        raise HTTPException(400, "Invalid domain")
    try:
        result = subprocess.run(
            ["certbot", "renew", "--cert-name", domain, "--non-interactive"],
            capture_output=True, timeout=120,
        )
        success = result.returncode == 0
        return {"success": success, "expires_at": _cert_expiry(domain) if success else None}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Remove Domain ──────────────────────────────────────────────────────────────

@router.delete("/{domain}")
async def remove_domain(domain: str, _=Depends(verify_internal_token)):
    domain = (domain or "").lower().strip()
    if not DOMAIN_RE.match(domain):
        raise HTTPException(400, "Invalid domain")
    try:
        # Remove vhost
        for path in (f"{NGINX_ENABLED}/{domain}.conf", f"{NGINX_SITES}/{domain}.conf"):
            if os.path.exists(path):
                os.remove(path)
        # Delete cert (best-effort)
        subprocess.run(
            ["certbot", "delete", "--cert-name", domain, "--non-interactive"],
            capture_output=True, timeout=60,
        )
        _reload_nginx()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _write_http_vhost(domain: str, port: int):
    """Write an initial HTTP vhost (certbot upgrades it to HTTPS)."""
    conf = f"""# Custom domain: {domain} (auto-generated)
server {{
    listen 80;
    server_name {domain};

    location /.well-known/acme-challenge/ {{
        root /var/www/html;
    }}

    location / {{
        proxy_pass http://127.0.0.1:{port};
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Real-IP $remote_addr;
    }}
}}
"""
    site_path = f"{NGINX_SITES}/{domain}.conf"
    enabled_path = f"{NGINX_ENABLED}/{domain}.conf"
    with open(site_path, "w") as f:
        f.write(conf)
    if not os.path.exists(enabled_path):
        os.symlink(site_path, enabled_path)


def _reload_nginx():
    test = subprocess.run(["nginx", "-t"], capture_output=True)
    if test.returncode != 0:
        raise RuntimeError(f"nginx config error: {test.stderr.decode()[-300:]}")
    subprocess.run(["nginx", "-s", "reload"], check=True)


def _cert_expiry(domain: str) -> Optional[str]:
    """Read cert expiry from the live cert PEM."""
    cert_path = f"{CERT_LIVE}/{domain}/cert.pem"
    if not os.path.exists(cert_path):
        return None
    try:
        result = subprocess.run(
            ["openssl", "x509", "-enddate", "-noout", "-in", cert_path],
            capture_output=True, timeout=10,
        )
        # Output: notAfter=Sep  1 00:00:00 2026 GMT
        line = result.stdout.decode().strip()
        date_str = line.split("=", 1)[1].strip()
        dt = datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z")
        return dt.isoformat()
    except Exception as e:
        _logger.warning("cert expiry parse failed for %s: %s", domain, e)
        return None


def _lookup_tenant_port(subdomain: str) -> Optional[int]:
    """Resolve a tenant's Odoo upstream port from the instances table."""
    try:
        from app.core.database import SyncSession
        from app.models.instance import Instance
        with SyncSession() as db:
            inst = db.query(Instance).filter(Instance.subdomain == subdomain).first()
            return inst.odoo_port if inst else None
    except Exception:
        return None
