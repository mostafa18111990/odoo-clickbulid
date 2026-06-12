#!/usr/bin/env python
"""Deploy complete SaaS platform - all backend + frontend"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN = "odoo.clickbulid.com"

def upload(remote_path, content):
    remote_dir = "/".join(remote_path.split("/")[:-1])
    client.exec_command(f"mkdir -p '{remote_dir}'"); time.sleep(0.1)
    sftp.putfo(io.BytesIO(content.encode('utf-8')), remote_path)
    print(f"  [OK] {remote_path}")

def run(cmd, timeout=15):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

# ══════════════════════════════════════════════════════════════════════════════
# 1. USER MODEL - add is_superuser
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1/8] Updating User model...")
upload('/opt/clickbuild/backend/app/models/user.py', '''\
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from app.core.database import Base


class UserLanguage(str, enum.Enum):
    AR = "ar"
    EN = "en"


class UserCountry(str, enum.Enum):
    EG = "EG"; SA = "SA"; AE = "AE"; KW = "KW"
    QA = "QA"; BH = "BH"; OM = "OM"; JO = "JO"; OTHER = "OTHER"


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name          = Column(String(100), nullable=False)
    phone         = Column(String(20),  nullable=True)
    company_name  = Column(String(100), nullable=True)
    country       = Column(Enum(UserCountry), default=UserCountry.EG)
    language      = Column(Enum(UserLanguage), default=UserLanguage.AR)

    is_verified       = Column(Boolean, default=False)
    is_active         = Column(Boolean, default=True)
    is_superuser      = Column(Boolean, default=False)   # Super Admin
    verification_code = Column(String(6),   nullable=True)
    reset_token       = Column(String(100), nullable=True)
    reset_token_exp   = Column(DateTime(timezone=True), nullable=True)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    instances     = relationship("Instance", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user")
''')

# ══════════════════════════════════════════════════════════════════════════════
# 2. INSTANCE MODEL - fix domain URL
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2/8] Updating Instance model...")
upload('/opt/clickbuild/backend/app/models/instance.py', f'''\
from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid, enum
from app.core.database import Base

DOMAIN = "{DOMAIN}"


class InstanceStatus(str, enum.Enum):
    PROVISIONING = "provisioning"
    RUNNING      = "running"
    STOPPED      = "stopped"
    SUSPENDED    = "suspended"
    EXPIRED      = "expired"
    UPGRADING    = "upgrading"
    ERROR        = "error"
    DELETED      = "deleted"


class Instance(Base):
    __tablename__ = "instances"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    subdomain    = Column(String(63),  unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=True)

    odoo_version        = Column(String(10),  default="19")
    odoo_version_target = Column(String(10),  nullable=True)
    container_id        = Column(String(100), nullable=True)
    container_name      = Column(String(100), nullable=True)
    db_name             = Column(String(100), nullable=True)
    odoo_port           = Column(Integer,     nullable=True)
    longpolling_port    = Column(Integer,     nullable=True)

    admin_email  = Column(String(255), nullable=True)
    admin_pass   = Column(String(255), nullable=True)

    status    = Column(Enum(InstanceStatus), default=InstanceStatus.PROVISIONING)
    error_msg = Column(Text, nullable=True)
    is_trial  = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    cpu_limit  = Column(Float,   default=1.0)
    memory_mb  = Column(Integer, default=1024)
    storage_gb = Column(Float,   default=1.0)

    user         = relationship("User", back_populates="instances")
    subscription = relationship("Subscription", back_populates="instance", uselist=False)

    @property
    def url(self):
        return f"https://{{self.subdomain}}.{DOMAIN}"
''')

# ══════════════════════════════════════════════════════════════════════════════
# 3. ADMIN ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3/8] Creating Admin API...")
upload('/opt/clickbuild/backend/app/api/v1/endpoints/admin.py', f'''\
"""Admin API - Super Admin endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timezone
from typing import Optional
import docker, subprocess, os
from pathlib import Path

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.instance import Instance, InstanceStatus
from app.models.subscription import Plan
from app.services.provisioning import ProvisioningEngine

router = APIRouter(prefix="/admin", tags=["admin"])
engine = ProvisioningEngine()


def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin only")
    return current_user


# ─── Platform Stats ───────────────────────────────────────────────────────────
@router.get("/stats")
async def platform_stats(
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    total_users     = (await db.execute(select(func.count(User.id)))).scalar()
    active_users    = (await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar()
    total_instances = (await db.execute(select(func.count(Instance.id)))).scalar()
    running         = (await db.execute(select(func.count(Instance.id)).where(Instance.status == InstanceStatus.RUNNING))).scalar()
    trial           = (await db.execute(select(func.count(Instance.id)).where(Instance.is_trial == True, Instance.status != InstanceStatus.DELETED))).scalar()
    errors          = (await db.execute(select(func.count(Instance.id)).where(Instance.status == InstanceStatus.ERROR))).scalar()

    # Server resources
    import psutil
    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Docker stats
    try:
        dc = docker.from_env()
        containers = dc.containers.list()
        docker_running = len(containers)
    except Exception:
        docker_running = 0

    return {{
        "users":     {{"total": total_users, "active": active_users}},
        "instances": {{"total": total_instances, "running": running, "trial": trial, "errors": errors}},
        "server":    {{
            "cpu_pct":   cpu,
            "ram_used_gb":  round(ram.used / 1e9, 2),
            "ram_total_gb": round(ram.total / 1e9, 2),
            "ram_pct":   ram.percent,
            "disk_used_gb":  round(disk.used / 1e9, 2),
            "disk_total_gb": round(disk.total / 1e9, 2),
            "disk_pct":  disk.percent,
        }},
        "docker": {{"running_containers": docker_running}},
    }}


# ─── Users Management ─────────────────────────────────────────────────────────
@router.get("/users")
async def list_users(
    page: int = 1, per_page: int = 20,
    search: Optional[str] = None,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    q = select(User).order_by(User.created_at.desc())
    if search:
        q = q.where(User.email.ilike(f"%{{search}}%") | User.name.ilike(f"%{{search}}%"))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset((page-1)*per_page).limit(per_page))
    users = result.scalars().all()

    return {{
        "total": total, "page": page, "per_page": per_page,
        "users": [{{
            "id": str(u.id), "email": u.email, "name": u.name,
            "company": u.company_name, "country": u.country,
            "is_active": u.is_active, "is_superuser": u.is_superuser,
            "is_verified": u.is_verified, "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
        }} for u in users]
    }}


@router.patch("/users/{{user_id}}")
async def update_user(
    user_id: str,
    body: dict,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    for field in ["is_active", "is_superuser"]:
        if field in body:
            setattr(user, field, body[field])

    await db.commit()
    return {{"ok": True}}


# ─── Instances Management ─────────────────────────────────────────────────────
@router.get("/instances")
async def list_all_instances(
    page: int = 1, per_page: int = 20,
    status_filter: Optional[str] = None,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    q = select(Instance, User).join(User, Instance.user_id == User.id).order_by(Instance.created_at.desc())
    if status_filter:
        q = q.where(Instance.status == status_filter)
    q = q.where(Instance.status != InstanceStatus.DELETED)

    total = (await db.execute(select(func.count(Instance.id)).where(Instance.status != InstanceStatus.DELETED))).scalar()
    result = await db.execute(q.offset((page-1)*per_page).limit(per_page))
    rows = result.all()

    return {{
        "total": total, "page": page, "per_page": per_page,
        "instances": [{{
            "id":          str(inst.id),
            "subdomain":   inst.subdomain,
            "url":         inst.url,
            "status":      inst.status,
            "odoo_version": inst.odoo_version,
            "is_trial":    inst.is_trial,
            "expires_at":  inst.expires_at.isoformat() if inst.expires_at else None,
            "created_at":  inst.created_at.isoformat() if inst.created_at else None,
            "cpu_limit":   inst.cpu_limit,
            "memory_mb":   inst.memory_mb,
            "port":        inst.odoo_port,
            "error_msg":   inst.error_msg,
            "user": {{
                "id": str(u.id), "email": u.email,
                "name": u.name, "company": u.company_name,
            }},
        }} for inst, u in rows]
    }}


@router.post("/instances/{{instance_id}}/suspend")
async def suspend_instance(
    instance_id: str,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")

    await engine.stop_instance(inst)
    inst.status = InstanceStatus.SUSPENDED
    await db.commit()
    return {{"ok": True, "status": "suspended"}}


@router.post("/instances/{{instance_id}}/resume")
async def resume_instance(
    instance_id: str,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")

    await engine.start_instance(inst)
    inst.status = InstanceStatus.RUNNING
    await db.commit()
    return {{"ok": True, "status": "running"}}


@router.delete("/instances/{{instance_id}}")
async def delete_instance(
    instance_id: str,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")

    await engine.delete_instance(db, inst)
    return {{"ok": True}}


# ─── Per-Instance Monitoring ──────────────────────────────────────────────────
@router.get("/instances/{{instance_id}}/stats")
async def instance_stats(
    instance_id: str,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")

    try:
        dc = docker.from_env()
        container = dc.containers.get(inst.container_name)
        raw = container.stats(stream=False)

        cpu_delta  = raw["cpu_stats"]["cpu_usage"]["total_usage"] - raw["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_delta  = raw["cpu_stats"]["system_cpu_usage"] - raw["precpu_stats"]["system_cpu_usage"]
        num_cpus   = raw["cpu_stats"].get("online_cpus", 1)
        cpu_pct    = round((cpu_delta / sys_delta) * num_cpus * 100, 2) if sys_delta > 0 else 0

        mem_used   = raw["memory_stats"]["usage"]
        mem_limit  = raw["memory_stats"]["limit"]
        mem_pct    = round(mem_used / mem_limit * 100, 2)

        net_in  = sum(v["rx_bytes"] for v in raw.get("networks", {{}}).values())
        net_out = sum(v["tx_bytes"] for v in raw.get("networks", {{}}).values())

        return {{
            "status":      container.status,
            "cpu_pct":     cpu_pct,
            "mem_used_mb": round(mem_used / 1e6, 1),
            "mem_limit_mb": round(mem_limit / 1e6, 1),
            "mem_pct":     mem_pct,
            "net_in_mb":   round(net_in / 1e6, 2),
            "net_out_mb":  round(net_out / 1e6, 2),
        }}
    except docker.errors.NotFound:
        return {{"status": "not_found", "cpu_pct": 0, "mem_used_mb": 0, "mem_limit_mb": 0, "mem_pct": 0}}
    except Exception as e:
        return {{"status": "error", "error": str(e)}}


# ─── Backup ───────────────────────────────────────────────────────────────────
@router.post("/instances/{{instance_id}}/backup")
async def backup_instance(
    instance_id: str,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    if not inst.db_name: raise HTTPException(400, "No DB configured")

    def do_backup():
        from app.core.config import settings
        backup_dir = Path("/opt/clickbuild/backups") / inst.subdomain
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"{{inst.db_name}}_{{ts}}.sql.gz"
        env  = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
        with open(dest, "wb") as f:
            pg = subprocess.Popen(
                ["pg_dump", "-h", settings.POSTGRES_HOST, "-U", settings.POSTGRES_USER,
                 "-d", inst.db_name, "--compress=9"],
                stdout=f, env=env
            )
            pg.wait()

    background_tasks.add_task(do_backup)
    return {{"ok": True, "message": "Backup started in background"}}


@router.get("/instances/{{instance_id}}/backups")
async def list_backups(
    instance_id: str,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")

    backup_dir = Path("/opt/clickbuild/backups") / inst.subdomain
    if not backup_dir.exists():
        return {{"backups": []}}

    backups = []
    for f in sorted(backup_dir.glob("*.sql.gz"), reverse=True)[:20]:
        stat = f.stat()
        backups.append({{
            "name": f.name,
            "size_mb": round(stat.st_size / 1e6, 2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        }})
    return {{"backups": backups}}


# ─── Logs ─────────────────────────────────────────────────────────────────────
@router.get("/instances/{{instance_id}}/logs")
async def instance_logs(
    instance_id: str,
    lines: int = 100,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")

    try:
        dc = docker.from_env()
        container = dc.containers.get(inst.container_name)
        logs = container.logs(tail=lines, timestamps=True).decode("utf-8", errors="replace")
        return {{"logs": logs, "lines": lines}}
    except docker.errors.NotFound:
        return {{"logs": "Container not found", "lines": 0}}
    except Exception as e:
        return {{"logs": str(e), "lines": 0}}
''')

# ══════════════════════════════════════════════════════════════════════════════
# 4. UPDATE MAIN.PY - add admin router
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4/8] Updating main.py...")
upload('/opt/clickbuild/backend/app/main.py', '''\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import create_tables
from app.api.v1.endpoints import auth, instances, payments, admin


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


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}
''')

# ══════════════════════════════════════════════════════════════════════════════
# 5. FRONTEND - Admin Dashboard
# ══════════════════════════════════════════════════════════════════════════════
print("\n[5/8] Creating Admin Dashboard frontend...")

upload('/opt/clickbuild/frontend/src/app/[locale]/admin/page.tsx', f'''\
'use client';
import {{ useState, useEffect }} from 'react';
import {{ useRouter }} from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

interface Stats {{
  users:     {{ total: number; active: number }};
  instances: {{ total: number; running: number; trial: number; errors: number }};
  server:    {{ cpu_pct: number; ram_used_gb: number; ram_total_gb: number; ram_pct: number; disk_used_gb: number; disk_total_gb: number; disk_pct: number }};
  docker:    {{ running_containers: number }};
}}

function Stat({{ label, value, sub, color = 'violet' }}: {{ label: string; value: string|number; sub?: string; color?: string }}) {{
  const colors: Record<string,string> = {{
    violet: 'bg-violet-50 border-violet-200 text-violet-700',
    green:  'bg-green-50 border-green-200 text-green-700',
    blue:   'bg-blue-50 border-blue-200 text-blue-700',
    orange: 'bg-orange-50 border-orange-200 text-orange-700',
    red:    'bg-red-50 border-red-200 text-red-700',
  }};
  return (
    <div className={{`border rounded-2xl p-5 ${{colors[color] || colors.violet}}`}}>
      <div className="text-3xl font-black">{{value}}</div>
      <div className="font-semibold mt-1">{{label}}</div>
      {{sub && <div className="text-xs opacity-70 mt-1">{{sub}}</div>}}
    </div>
  );
}}

function ProgressBar({{ pct, color='violet' }}: {{ pct: number; color?: string }}) {{
  const bg = color === 'red' ? 'bg-red-500' : color === 'orange' ? 'bg-orange-500' : 'bg-violet-500';
  return (
    <div className="w-full bg-gray-200 rounded-full h-2.5 mt-1">
      <div className={{`${{bg}} h-2.5 rounded-full`}} style={{{{ width: `${{Math.min(pct,100)}}%` }}}} />
    </div>
  );
}}

export default function AdminPage() {{
  const router = useRouter();
  const [stats, setStats]     = useState<Stats|null>(null);
  const [instances, setInsts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken]     = useState('');

  useEffect(() => {{
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) {{ router.push('/login'); return; }}
    const auth = JSON.parse(stored);
    const t = auth?.state?.accessToken;
    if (!t) {{ router.push('/login'); return; }}
    setToken(t);
    loadAll(t);
    const iv = setInterval(() => loadAll(t), 30000);
    return () => clearInterval(iv);
  }}, []);

  async function loadAll(t: string) {{
    try {{
      const [sRes, iRes] = await Promise.all([
        fetch(`${{API}}/admin/stats`, {{ headers: {{ Authorization: `Bearer ${{t}}` }} }}),
        fetch(`${{API}}/admin/instances?per_page=10`, {{ headers: {{ Authorization: `Bearer ${{t}}` }} }}),
      ]);
      if (sRes.status === 403) {{ router.push('/dashboard'); return; }}
      if (sRes.ok) setStats(await sRes.json());
      if (iRes.ok) setInsts((await iRes.json()).instances || []);
    }} finally {{
      setLoading(false);
    }}
  }}

  async function action(instanceId: string, act: string) {{
    const method = act === 'delete' ? 'DELETE' : 'POST';
    const url    = act === 'delete'
      ? `${{API}}/admin/instances/${{instanceId}}`
      : `${{API}}/admin/instances/${{instanceId}}/${{act}}`;
    await fetch(url, {{ method, headers: {{ Authorization: `Bearer ${{token}}` }} }});
    loadAll(token);
  }}

  if (loading) return <div className="flex items-center justify-center h-screen text-gray-400">جاري التحميل...</div>;

  const s = stats?.server;

  return (
    <div className="min-h-screen bg-gray-50">
      {{/* Header */}}
      <header className="bg-white border-b px-6 h-16 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <span className="font-black text-xl text-violet-700">OdooClickBuild</span>
          <span className="bg-red-100 text-red-700 text-xs font-bold px-2 py-0.5 rounded-full">Super Admin</span>
        </div>
        <div className="flex gap-4">
          <Link href="/admin/instances" className="text-sm text-gray-600 hover:text-violet-700">جميع البيئات</Link>
          <Link href="/admin/users"     className="text-sm text-gray-600 hover:text-violet-700">المستخدمون</Link>
          <Link href="/dashboard"       className="text-sm text-gray-500">لوحة المستخدم</Link>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-black mb-6">لوحة التحكم الرئيسية</h1>

        {{/* Stats Grid */}}
        {{stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <Stat label="إجمالي المستخدمين"  value={{stats.users.total}}     sub={{`${{stats.users.active}} نشط`}}     color="violet" />
            <Stat label="البيئات الكلية"       value={{stats.instances.total}} sub={{`${{stats.instances.running}} تعمل`}} color="green"  />
            <Stat label="نسخ تجريبية"          value={{stats.instances.trial}} sub="نشطة الآن"                            color="blue"   />
            <Stat label="أخطاء"               value={{stats.instances.errors}} sub="تحتاج مراجعة"                        color={{stats.instances.errors > 0 ? 'red' : 'green'}} />
          </div>
        )}}

        {{/* Server Resources */}}
        {{s && (
          <div className="bg-white rounded-2xl border p-6 mb-8 shadow-sm">
            <h2 className="font-black text-lg mb-4">موارد السيرفر</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <div className="flex justify-between text-sm font-medium">
                  <span>CPU</span>
                  <span className={{s.cpu_pct > 80 ? 'text-red-600' : 'text-green-600'}}>{{s.cpu_pct}}%</span>
                </div>
                <ProgressBar pct={{s.cpu_pct}} color={{s.cpu_pct > 80 ? 'red' : s.cpu_pct > 60 ? 'orange' : 'violet'}} />
              </div>
              <div>
                <div className="flex justify-between text-sm font-medium">
                  <span>RAM</span>
                  <span>{{s.ram_used_gb}} / {{s.ram_total_gb}} GB ({{s.ram_pct}}%)</span>
                </div>
                <ProgressBar pct={{s.ram_pct}} color={{s.ram_pct > 85 ? 'red' : s.ram_pct > 70 ? 'orange' : 'violet'}} />
              </div>
              <div>
                <div className="flex justify-between text-sm font-medium">
                  <span>القرص</span>
                  <span>{{s.disk_used_gb}} / {{s.disk_total_gb}} GB ({{s.disk_pct}}%)</span>
                </div>
                <ProgressBar pct={{s.disk_pct}} color={{s.disk_pct > 85 ? 'red' : s.disk_pct > 70 ? 'orange' : 'violet'}} />
              </div>
            </div>
            <div className="mt-4 text-sm text-gray-500">
              Docker: {{stats?.docker.running_containers}} حاوية تعمل
            </div>
          </div>
        )}}

        {{/* Recent Instances */}}
        <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b flex justify-between items-center">
            <h2 className="font-black text-lg">أحدث البيئات</h2>
            <Link href="/admin/instances" className="text-sm text-violet-600 hover:underline">عرض الكل</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {{['النطاق','العميل','الإصدار','الحالة','انتهاء','إجراء'].map(h => (
                    <th key={{h}} className="text-right px-4 py-3 font-semibold text-gray-600">{{h}}</th>
                  ))}}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {{instances.map(inst => (
                  <tr key={{inst.id}} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <a href={{inst.url}} target="_blank" className="text-violet-600 hover:underline font-medium">
                        {{inst.subdomain}}
                      </a>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{{inst.user?.email}}</td>
                    <td className="px-4 py-3">Odoo {{inst.odoo_version}}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={{inst.status}} />
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {{inst.expires_at ? new Date(inst.expires_at).toLocaleDateString('ar-EG') : '—'}}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <Link href={{`/admin/instances/${{inst.id}}`}}
                          className="text-xs bg-gray-100 hover:bg-gray-200 px-2 py-1 rounded-lg">
                          تفاصيل
                        </Link>
                        {{inst.status === 'running' ? (
                          <button onClick={{() => action(inst.id, 'suspend')}}
                            className="text-xs bg-orange-100 hover:bg-orange-200 text-orange-700 px-2 py-1 rounded-lg">
                            إيقاف
                          </button>
                        ) : inst.status === 'suspended' ? (
                          <button onClick={{() => action(inst.id, 'resume')}}
                            className="text-xs bg-green-100 hover:bg-green-200 text-green-700 px-2 py-1 rounded-lg">
                            تشغيل
                          </button>
                        ) : null}}
                      </div>
                    </td>
                  </tr>
                ))}}
              </tbody>
            </table>
            {{instances.length === 0 && (
              <div className="text-center py-12 text-gray-400">لا توجد بيئات بعد</div>
            )}}
          </div>
        </div>
      </main>
    </div>
  );
}}

function StatusBadge({{ status }}: {{ status: string }}) {{
  const map: Record<string,[string,string]> = {{
    running:      ['يعمل',         'bg-green-100 text-green-700'],
    stopped:      ['متوقف',        'bg-gray-100 text-gray-600'],
    suspended:    ['موقوف',        'bg-orange-100 text-orange-700'],
    provisioning: ['جاري الإنشاء', 'bg-blue-100 text-blue-700'],
    error:        ['خطأ',          'bg-red-100 text-red-700'],
    expired:      ['منتهي',        'bg-red-100 text-red-600'],
    upgrading:    ['ترقية',        'bg-purple-100 text-purple-700'],
  }};
  const [label, cls] = map[status] || [status, 'bg-gray-100 text-gray-600'];
  return <span className={{`text-xs font-medium px-2 py-0.5 rounded-full ${{cls}}`}}>{{label}}</span>;
}}
''')

# Instance detail page
upload('/opt/clickbuild/frontend/src/app/[locale]/admin/instances/[id]/page.tsx', f'''\
'use client';
import {{ useState, useEffect }} from 'react';
import {{ useRouter, useParams }} from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

export default function InstanceDetailPage() {{
  const router = useRouter();
  const {{ id }} = useParams();
  const [inst, setInst]   = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [logs, setLogs]   = useState('');
  const [backups, setBackups] = useState<any[]>([]);
  const [token, setToken] = useState('');
  const [tab, setTab]     = useState<'overview'|'logs'|'backups'>('overview');

  useEffect(() => {{
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) {{ router.push('/login'); return; }}
    const t = JSON.parse(stored)?.state?.accessToken;
    setToken(t);
    loadData(t);
  }}, []);

  async function loadData(t: string) {{
    const headers = {{ Authorization: `Bearer ${{t}}` }};
    const [instRes, statsRes, logsRes, backRes] = await Promise.all([
      fetch(`${{API}}/admin/instances?per_page=200`, {{ headers }}),
      fetch(`${{API}}/admin/instances/${{id}}/stats`, {{ headers }}),
      fetch(`${{API}}/admin/instances/${{id}}/logs?lines=50`, {{ headers }}),
      fetch(`${{API}}/admin/instances/${{id}}/backups`, {{ headers }}),
    ]);
    if (instRes.ok) {{
      const data = await instRes.json();
      const found = data.instances?.find((i: any) => i.id === id);
      setInst(found);
    }}
    if (statsRes.ok) setStats(await statsRes.json());
    if (logsRes.ok)  setLogs((await logsRes.json()).logs || '');
    if (backRes.ok)  setBackups((await backRes.json()).backups || []);
  }}

  async function triggerBackup() {{
    await fetch(`${{API}}/admin/instances/${{id}}/backup`, {{
      method: 'POST', headers: {{ Authorization: `Bearer ${{token}}` }}
    }});
    alert('Backup started!');
  }}

  async function suspendResume() {{
    const act = inst.status === 'running' ? 'suspend' : 'resume';
    await fetch(`${{API}}/admin/instances/${{id}}/${{act}}`, {{
      method: 'POST', headers: {{ Authorization: `Bearer ${{token}}` }}
    }});
    loadData(token);
  }}

  if (!inst) return <div className="flex items-center justify-center h-screen text-gray-400">جاري التحميل...</div>;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 h-14 flex items-center gap-3 shadow-sm">
        <Link href="/admin" className="text-gray-400 hover:text-gray-600">← Admin</Link>
        <span className="text-gray-300">|</span>
        <span className="font-bold text-violet-700">{{inst.subdomain}}.{DOMAIN}</span>
        <span className={{`text-xs px-2 py-0.5 rounded-full font-medium ${{inst.status === 'running' ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'}}`}}>
          {{inst.status}}
        </span>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {{/* Action bar */}}
        <div className="flex gap-3 mb-6">
          <a href={{inst.url}} target="_blank"
            className="bg-violet-700 text-white px-4 py-2 rounded-xl text-sm font-medium hover:bg-violet-800 transition">
            فتح Odoo
          </a>
          <button onClick={{suspendResume}}
            className={{`px-4 py-2 rounded-xl text-sm font-medium transition ${{inst.status === 'running' ? 'bg-orange-100 text-orange-700 hover:bg-orange-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}}`}}>
            {{inst.status === 'running' ? 'إيقاف مؤقت' : 'تشغيل'}}
          </button>
          <button onClick={{triggerBackup}}
            className="bg-blue-100 text-blue-700 px-4 py-2 rounded-xl text-sm font-medium hover:bg-blue-200 transition">
            نسخ احتياطي
          </button>
        </div>

        {{/* Tabs */}}
        <div className="flex gap-1 mb-6 bg-white border rounded-xl p-1 w-fit">
          {{(['overview','logs','backups'] as const).map(t => (
            <button key={{t}} onClick={{() => setTab(t)}}
              className={{`px-4 py-1.5 rounded-lg text-sm font-medium transition ${{tab === t ? 'bg-violet-700 text-white' : 'text-gray-600 hover:bg-gray-100'}}`}}>
              {{t === 'overview' ? 'نظرة عامة' : t === 'logs' ? 'سجلات' : 'نسخ احتياطية'}}
            </button>
          ))}}
        </div>

        {{tab === 'overview' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl border p-5 shadow-sm">
              <h3 className="font-bold mb-4">معلومات البيئة</h3>
              <dl className="space-y-2 text-sm">
                {{[
                  ['النطاق', inst.subdomain],
                  ['الإصدار', `Odoo ${{inst.odoo_version}}`],
                  ['المنفذ', inst.port],
                  ['قاعدة البيانات', inst.db_name || '—'],
                  ['تجريبي', inst.is_trial ? 'نعم' : 'لا'],
                  ['تاريخ الإنشاء', new Date(inst.created_at).toLocaleDateString('ar-EG')],
                  ['تاريخ الانتهاء', inst.expires_at ? new Date(inst.expires_at).toLocaleDateString('ar-EG') : 'لا ينتهي'],
                  ['المستخدم', inst.user?.email],
                ].map(([k, v]) => (
                  <div key={{String(k)}} className="flex justify-between">
                    <dt className="text-gray-500">{{k}}</dt>
                    <dd className="font-medium">{{String(v)}}</dd>
                  </div>
                ))}}
              </dl>
            </div>

            {{stats && (
              <div className="bg-white rounded-2xl border p-5 shadow-sm">
                <h3 className="font-bold mb-4">موارد الحاوية</h3>
                {{[
                  ['CPU', `${{stats.cpu_pct}}%`],
                  ['RAM', `${{stats.mem_used_mb}} / ${{stats.mem_limit_mb}} MB (${{stats.mem_pct}}%)`],
                  ['شبكة داخل', `${{stats.net_in_mb}} MB`],
                  ['شبكة خارج', `${{stats.net_out_mb}} MB`],
                ].map(([k, v]) => (
                  <div key={{String(k)}} className="flex justify-between text-sm py-1.5 border-b last:border-0">
                    <span className="text-gray-500">{{k}}</span>
                    <span className="font-medium">{{String(v)}}</span>
                  </div>
                ))}}
              </div>
            )}}
          </div>
        )}}

        {{tab === 'logs' && (
          <div className="bg-gray-900 rounded-2xl p-4 overflow-auto max-h-[500px]">
            <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap">{{logs || 'لا توجد سجلات'}}</pre>
          </div>
        )}}

        {{tab === 'backups' && (
          <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {{['اسم الملف','الحجم','التاريخ'].map(h => (
                    <th key={{h}} className="text-right px-4 py-3 font-semibold text-gray-600">{{h}}</th>
                  ))}}
                </tr>
              </thead>
              <tbody className="divide-y">
                {{backups.map(b => (
                  <tr key={{b.name}} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs">{{b.name}}</td>
                    <td className="px-4 py-3">{{b.size_mb}} MB</td>
                    <td className="px-4 py-3 text-gray-500">{{new Date(b.created_at).toLocaleString('ar-EG')}}</td>
                  </tr>
                ))}}
              </tbody>
            </table>
            {{backups.length === 0 && <div className="text-center py-8 text-gray-400">لا توجد نسخ احتياطية</div>}}
          </div>
        )}}
      </main>
    </div>
  );
}}
''')

# All Instances page
upload('/opt/clickbuild/frontend/src/app/[locale]/admin/instances/page.tsx', f'''\
'use client';
import {{ useState, useEffect }} from 'react';
import {{ useRouter }} from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

const STATUS_LABELS: Record<string,string> = {{
  running:'يعمل', stopped:'متوقف', suspended:'موقوف',
  provisioning:'إنشاء', error:'خطأ', expired:'منتهي', upgrading:'ترقية',
}};
const STATUS_COLORS: Record<string,string> = {{
  running:'bg-green-100 text-green-700', stopped:'bg-gray-100 text-gray-600',
  suspended:'bg-orange-100 text-orange-700', provisioning:'bg-blue-100 text-blue-700',
  error:'bg-red-100 text-red-700', expired:'bg-red-50 text-red-600',
}};

export default function AllInstancesPage() {{
  const router = useRouter();
  const [instances, setInstances] = useState<any[]>([]);
  const [total, setTotal]         = useState(0);
  const [page, setPage]           = useState(1);
  const [filter, setFilter]       = useState('');
  const [token, setToken]         = useState('');
  const [loading, setLoading]     = useState(true);

  useEffect(() => {{
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) {{ router.push('/login'); return; }}
    const t = JSON.parse(stored)?.state?.accessToken;
    setToken(t);
    loadInstances(t, 1, filter);
  }}, []);

  async function loadInstances(t: string, p: number, f: string) {{
    setLoading(true);
    const params = new URLSearchParams({{ page: String(p), per_page: '20' }});
    if (f) params.set('status_filter', f);
    const res = await fetch(`${{API}}/admin/instances?${{params}}`, {{
      headers: {{ Authorization: `Bearer ${{t}}` }}
    }});
    if (res.ok) {{
      const data = await res.json();
      setInstances(data.instances || []);
      setTotal(data.total || 0);
    }}
    setLoading(false);
  }}

  async function action(id: string, act: string) {{
    const method = act === 'delete' ? 'DELETE' : 'POST';
    const url    = act === 'delete' ? `${{API}}/admin/instances/${{id}}` : `${{API}}/admin/instances/${{id}}/${{act}}`;
    await fetch(url, {{ method, headers: {{ Authorization: `Bearer ${{token}}` }} }});
    loadInstances(token, page, filter);
  }}

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 h-14 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <Link href="/admin" className="text-gray-400 hover:text-violet-700">← Admin</Link>
          <span className="font-bold">جميع البيئات</span>
          <span className="text-sm text-gray-400">(${{total}})</span>
        </div>
        <select value={{filter}} onChange={{e => {{ setFilter(e.target.value); loadInstances(token, 1, e.target.value); }}}}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5">
          <option value="">جميع الحالات</option>
          {{Object.entries(STATUS_LABELS).map(([v,l]) => <option key={{v}} value={{v}}>{{l}}</option>)}}
        </select>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {{['النطاق','العميل','الإصدار','الحالة','المنفذ','الانتهاء','إجراءات'].map(h => (
                  <th key={{h}} className="text-right px-4 py-3 font-semibold text-gray-600">{{h}}</th>
                ))}}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {{instances.map(inst => (
                <tr key={{inst.id}} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link href={{`/admin/instances/${{inst.id}}`}} className="text-violet-600 hover:underline font-medium">
                      {{inst.subdomain}}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">
                    <div>{{inst.user?.name}}</div>
                    <div className="text-gray-400">{{inst.user?.email}}</div>
                  </td>
                  <td className="px-4 py-3">{{inst.odoo_version}}</td>
                  <td className="px-4 py-3">
                    <span className={{`text-xs font-medium px-2 py-0.5 rounded-full ${{STATUS_COLORS[inst.status] || 'bg-gray-100'}}`}}>
                      {{STATUS_LABELS[inst.status] || inst.status}}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{{inst.port || '—'}}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {{inst.expires_at ? new Date(inst.expires_at).toLocaleDateString('ar-EG') : '—'}}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5">
                      {{inst.status === 'running' && (
                        <button onClick={{() => action(inst.id, 'suspend')}}
                          className="text-xs bg-orange-100 text-orange-700 hover:bg-orange-200 px-2 py-1 rounded-lg">
                          إيقاف
                        </button>
                      )}}
                      {{inst.status === 'suspended' && (
                        <button onClick={{() => action(inst.id, 'resume')}}
                          className="text-xs bg-green-100 text-green-700 hover:bg-green-200 px-2 py-1 rounded-lg">
                          تشغيل
                        </button>
                      )}}
                      <button onClick={{() => action(inst.id, 'backup')}}
                        className="text-xs bg-blue-100 text-blue-700 hover:bg-blue-200 px-2 py-1 rounded-lg">
                        نسخ
                      </button>
                      <button onClick={{() => {{ if(confirm('حذف البيئة؟')) action(inst.id,'delete') }}}}
                        className="text-xs bg-red-100 text-red-700 hover:bg-red-200 px-2 py-1 rounded-lg">
                        حذف
                      </button>
                    </div>
                  </td>
                </tr>
              ))}}
            </tbody>
          </table>
          {{loading && <div className="text-center py-8 text-gray-400">جاري التحميل...</div>}}
          {{!loading && instances.length === 0 && <div className="text-center py-8 text-gray-400">لا توجد بيئات</div>}}
        </div>

        {{/* Pagination */}}
        {{total > 20 && (
          <div className="flex justify-center gap-2 mt-4">
            {{Array.from({{length: Math.ceil(total/20)}}).map((_,i) => (
              <button key={{i}} onClick={{() => {{ setPage(i+1); loadInstances(token,i+1,filter); }}}}
                className={{`px-3 py-1.5 rounded-lg text-sm ${{page===i+1 ? 'bg-violet-700 text-white' : 'bg-white border hover:bg-gray-50'}}`}}>
                {{i+1}}
              </button>
            ))}}
          </div>
        )}}
      </main>
    </div>
  );
}}
''')

# Users management page
upload('/opt/clickbuild/frontend/src/app/[locale]/admin/users/page.tsx', '''\
'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

const API = process.env.NEXT_PUBLIC_API_URL ?? '/api/v1';

export default function AdminUsersPage() {
  const router = useRouter();
  const [users, setUsers]   = useState<any[]>([]);
  const [total, setTotal]   = useState(0);
  const [search, setSearch] = useState('');
  const [token, setToken]   = useState('');

  useEffect(() => {
    const stored = localStorage.getItem('clickbuild-auth');
    if (!stored) { router.push('/login'); return; }
    const t = JSON.parse(stored)?.state?.accessToken;
    setToken(t);
    load(t, '');
  }, []);

  async function load(t: string, q: string) {
    const params = new URLSearchParams({ per_page: '50' });
    if (q) params.set('search', q);
    const res = await fetch(`${API}/admin/users?${params}`, { headers: { Authorization: `Bearer ${t}` } });
    if (res.ok) { const d = await res.json(); setUsers(d.users||[]); setTotal(d.total||0); }
  }

  async function toggleActive(userId: string, current: boolean) {
    await fetch(`${API}/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !current }),
    });
    load(token, search);
  }

  async function toggleAdmin(userId: string, current: boolean) {
    await fetch(`${API}/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_superuser: !current }),
    });
    load(token, search);
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b px-6 h-14 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <Link href="/admin" className="text-gray-400 hover:text-violet-700">← Admin</Link>
          <span className="font-bold">المستخدمون</span>
          <span className="text-sm text-gray-400">({total})</span>
        </div>
        <input
          type="search" placeholder="ابحث بالاسم أو الإيميل..."
          value={search}
          onChange={e => { setSearch(e.target.value); load(token, e.target.value); }}
          className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-violet-400"
        />
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="bg-white rounded-2xl border shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                {['الاسم','الإيميل','الدولة','التحقق','نشط','Admin','تسجيل','إجراء'].map(h => (
                  <th key={h} className="text-right px-4 py-3 font-semibold text-gray-600">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{u.name}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{u.email}</td>
                  <td className="px-4 py-3 text-gray-500">{u.country}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${u.is_verified ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {u.is_verified ? 'مؤكد' : 'غير مؤكد'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
                      {u.is_active ? 'نشط' : 'موقوف'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {u.is_superuser && <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Admin</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('ar-EG') : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1.5">
                      <button onClick={() => toggleActive(u.id, u.is_active)}
                        className={`text-xs px-2 py-1 rounded-lg ${u.is_active ? 'bg-red-100 text-red-700 hover:bg-red-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}`}>
                        {u.is_active ? 'إيقاف' : 'تفعيل'}
                      </button>
                      <button onClick={() => toggleAdmin(u.id, u.is_superuser)}
                        className="text-xs bg-gray-100 text-gray-600 hover:bg-gray-200 px-2 py-1 rounded-lg">
                        {u.is_superuser ? 'إزالة Admin' : 'تعيين Admin'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length === 0 && <div className="text-center py-8 text-gray-400">لا يوجد مستخدمون</div>}
        </div>
      </main>
    </div>
  );
}
''')

# ══════════════════════════════════════════════════════════════════════════════
# 6. INSTALL psutil on server
# ══════════════════════════════════════════════════════════════════════════════
print("\n[6/8] Installing psutil...")
out, err = run(
    "cd /opt/clickbuild/backend && source venv/bin/activate && pip install psutil -q && echo PSUTIL_OK",
    timeout=60
)
print(out.strip() or err[:200])

# ══════════════════════════════════════════════════════════════════════════════
# 7. DB MIGRATION - add is_superuser column
# ══════════════════════════════════════════════════════════════════════════════
print("\n[7/8] Running DB migration...")
migrate_script = '''\
import asyncio, sys
sys.path.insert(0, '/opt/clickbuild/backend')
from app.models import user, instance, subscription
from app.core.database import async_engine, Base
from sqlalchemy import text

async def main():
    # Add is_superuser column if not exists
    async with async_engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_superuser BOOLEAN DEFAULT FALSE"
        ))
        # Also add suspended status to instances if not exists
        await conn.execute(text(
            "ALTER TABLE instances DROP CONSTRAINT IF EXISTS instances_status_check"
        ))
        # Recreate the enum type if needed
        try:
            await conn.execute(text("ALTER TYPE instancestatus ADD VALUE IF NOT EXISTS 'suspended'"))
        except Exception as e:
            pass  # already exists
        print("MIGRATION_OK")

asyncio.run(main())
'''
sftp.putfo(io.BytesIO(migrate_script.encode()), '/tmp/migrate.py')
out, err = run(
    "cd /opt/clickbuild/backend && source venv/bin/activate && python /tmp/migrate.py 2>&1",
    timeout=30
)
print(out.strip() or err[:200])

# ══════════════════════════════════════════════════════════════════════════════
# 8. Nginx directory for instances + Docker network
# ══════════════════════════════════════════════════════════════════════════════
print("\n[8/8] Setup Nginx instances dir + Docker network...")
cmds = [
    "mkdir -p /etc/nginx/sites-available/instances",
    "mkdir -p /opt/clickbuild/backups",
    "mkdir -p /opt/clickbuild/data",
    # Create Docker network for instances
    "docker network create clickbuild-net 2>/dev/null || echo 'Network already exists'",
    # Restart API
    "systemctl restart clickbuild-api && sleep 3 && curl -s http://127.0.0.1:8000/api/health",
]
for cmd in cmds:
    out, err = run(cmd, timeout=15)
    print(f"  > {out.strip() or err.strip()[:80]}")

sftp.close()

# ══════════════════════════════════════════════════════════════════════════════
# BUILD FRONTEND
# ══════════════════════════════════════════════════════════════════════════════
print("\n\nBuilding frontend...")
import time
build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -15"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
b_code = stdout.channel.recv_exit_status()
print(f"\nBuild: {b_code}")

if b_code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | grep -E 'online|error' | head -2")
    print(stdout.read().decode())

client.close()
print("\nDeployment complete!")
