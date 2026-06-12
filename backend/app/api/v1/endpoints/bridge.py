"""
Bridge Endpoints — FastAPI side of the Odoo↔FastAPI bridge.

These endpoints are called BY Odoo (saas_core, saas_marketplace,
saas_monitoring) to perform infrastructure operations that must run
on the host (Docker, certbot, module install) — never inside Odoo.

Security: all endpoints require the internal bearer token shared with
Odoo (saas.config.api_internal_token == settings.INTERNAL_API_TOKEN).

Routes (mounted under /api/v1):
  GET    /bridge/ping
  POST   /tenants/{instance_id}/apps/install      (Phase 10)
  POST   /tenants/{instance_id}/apps/uninstall    (Phase 10)
  GET    /instances/{instance_id}/health          (Phase 19)
"""
from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from typing import Optional
import subprocess
import logging
import docker

from app.core.config import settings

_logger = logging.getLogger(__name__)
router = APIRouter(tags=["bridge"])

_docker = docker.from_env()


# ─── Auth dependency ────────────────────────────────────────────────────────────

def verify_internal_token(authorization: str = Header(None)):
    """Validate the shared internal token from Odoo."""
    expected = f"Bearer {settings.INTERNAL_API_TOKEN}"
    if not authorization or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal token",
        )
    return True


# ─── Schemas ────────────────────────────────────────────────────────────────────

class AppInstallRequest(BaseModel):
    tenant_db: str
    tenant_subdomain: str
    module: str
    api_instance_id: Optional[str] = None


class AppUninstallRequest(BaseModel):
    tenant_db: str
    module: str


# ─── Ping ───────────────────────────────────────────────────────────────────────

@router.get("/bridge/ping")
async def ping(_=Depends(verify_internal_token)):
    return {"status": "ok", "service": "clickbuild-bridge"}


# ─── App Install / Uninstall (Phase 10: saas_marketplace) ───────────────────────

@router.post("/tenants/{instance_id}/apps/install")
async def install_app(
    instance_id: str,
    body: AppInstallRequest,
    _=Depends(verify_internal_token),
):
    """
    Install an Odoo module into a tenant's database.
    Runs: odoo -d <db> -i <module> --stop-after-init inside the tenant container.
    """
    container_name = body.tenant_subdomain and f"odoo_{body.tenant_subdomain}"
    module = _sanitize_module(body.module)
    if not module:
        raise HTTPException(400, "Invalid module name")

    try:
        container = _docker.containers.get(container_name)
    except docker.errors.NotFound:
        # Fallback: run via the shared image against the tenant DB
        return _install_via_exec(body.tenant_db, module)

    try:
        # exec inside the running tenant container
        exit_code, output = container.exec_run(
            cmd=[
                "odoo", "-d", body.tenant_db,
                "-i", module,
                "--stop-after-init",
                "--no-http",
            ],
            user="odoo",
        )
        out = output.decode("utf-8", errors="ignore")[-2000:]
        if exit_code == 0:
            _logger.info("Installed %s in %s", module, body.tenant_db)
            return {"success": True, "module": module, "log": out[-500:]}
        else:
            _logger.error("Install %s failed (%s): %s", module, exit_code, out[-500:])
            return {"success": False, "error": f"exit {exit_code}", "log": out[-500:]}
    except Exception as e:
        _logger.error("App install error: %s", e)
        return {"success": False, "error": str(e)}


@router.post("/tenants/{instance_id}/apps/uninstall")
async def uninstall_app(
    instance_id: str,
    body: AppUninstallRequest,
    _=Depends(verify_internal_token),
):
    """
    Uninstall an Odoo module from a tenant's database.
    Uses Odoo's module uninstall via a short python script (button_immediate_uninstall).
    """
    module = _sanitize_module(body.module)
    if not module:
        raise HTTPException(400, "Invalid module name")

    script = (
        "env['ir.module.module'].search(["
        f"('name','=','{module}'),('state','=','installed')"
        "]).button_immediate_uninstall()"
    )
    return _run_odoo_shell(body.tenant_db, script, action=f"uninstall {module}")


# ─── Tenant Health (Phase 19: saas_monitoring) ──────────────────────────────────

@router.get("/instances/{instance_id}/health")
async def instance_health(
    instance_id: str,
    _=Depends(verify_internal_token),
):
    """
    Report health of a tenant container: running state + resource usage.
    Odoo's HealthService calls this every 5 minutes.
    """
    # instance_id is the FastAPI Instance UUID; resolve container by lookup
    # In practice we accept the container via subdomain too; here we scan.
    try:
        # Find the instance record to get container_name
        from app.core.database import SyncSession
        from app.models.instance import Instance
        with SyncSession() as db:
            inst = db.query(Instance).filter(Instance.id == instance_id).first()
            if not inst or not inst.container_name:
                return {"healthy": False, "reason": "instance not found"}
            container_name = inst.container_name
    except Exception:
        # Fallback: treat instance_id as container name
        container_name = instance_id

    try:
        container = _docker.containers.get(container_name)
    except docker.errors.NotFound:
        return {"healthy": False, "reason": "container not found", "cpu_percent": 0, "memory_mb": 0}

    if container.status != "running":
        return {"healthy": False, "reason": f"status={container.status}",
                "cpu_percent": 0, "memory_mb": 0}

    # Resource stats (single sample)
    try:
        stats = container.stats(stream=False)
        cpu_pct = _calc_cpu_percent(stats)
        mem_mb = round(stats["memory_stats"].get("usage", 0) / (1024 * 1024), 1)
    except Exception:
        cpu_pct, mem_mb = 0.0, 0.0

    return {
        "healthy": True,
        "status": container.status,
        "cpu_percent": cpu_pct,
        "memory_mb": mem_mb,
    }


# ─── Helpers ────────────────────────────────────────────────────────────────────

def _sanitize_module(name: str) -> str:
    """Allow only valid Odoo module names (alphanumeric + underscore)."""
    import re
    name = (name or "").strip()
    return name if re.match(r"^[a-z0-9_]+$", name) else ""


def _install_via_exec(tenant_db: str, module: str) -> dict:
    """Fallback install via the shared odoo image against a tenant DB."""
    try:
        result = subprocess.run(
            [
                "docker", "exec", "odoo_saas_app",
                "odoo", "-d", tenant_db, "-i", module,
                "--stop-after-init", "--no-http",
            ],
            capture_output=True, timeout=300,
        )
        out = result.stdout.decode("utf-8", errors="ignore")[-500:]
        return {
            "success": result.returncode == 0,
            "module": module,
            "log": out,
            "error": None if result.returncode == 0 else f"exit {result.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "install timeout (still running)", "pending": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_odoo_shell(tenant_db: str, script: str, action: str) -> dict:
    """Run a python snippet via odoo shell against a tenant DB."""
    try:
        result = subprocess.run(
            ["docker", "exec", "-i", "odoo_saas_app",
             "odoo", "shell", "-d", tenant_db, "--no-http"],
            input=(script + "\nenv.cr.commit()\n").encode(),
            capture_output=True, timeout=180,
        )
        return {
            "success": result.returncode == 0,
            "action": action,
            "error": None if result.returncode == 0 else result.stderr.decode()[-500:],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _calc_cpu_percent(stats: dict) -> float:
    """Compute CPU % from Docker stats sample."""
    try:
        cpu = stats["cpu_stats"]
        precpu = stats["precpu_stats"]
        cpu_delta = cpu["cpu_usage"]["total_usage"] - precpu["cpu_usage"]["total_usage"]
        sys_delta = cpu["system_cpu_usage"] - precpu.get("system_cpu_usage", 0)
        online = cpu.get("online_cpus", 1) or 1
        if sys_delta > 0 and cpu_delta > 0:
            return round((cpu_delta / sys_delta) * online * 100, 1)
    except (KeyError, ZeroDivisionError, TypeError):
        pass
    return 0.0
