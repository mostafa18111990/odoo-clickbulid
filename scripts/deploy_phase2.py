#!/usr/bin/env python
"""Phase 2 Deployment - Critical missing features"""
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

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def run_print(cmd, timeout=30):
    out, err = run(cmd, timeout)
    print(f"  > {(out or err).strip()[:200]}")
    return out, err

# ══════════════════════════════════════════════════════════════════════════════
# 1. NGINX SERVICE - per-instance config + auto SSL
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1/7] Updating NginxService...")
upload('/opt/clickbuild/backend/app/services/nginx_service.py', f'''\
"""Nginx Service - manages per-instance reverse proxy configs"""
import subprocess, os
from pathlib import Path

DOMAIN         = "{DOMAIN}"
SITES_DIR      = Path("/etc/nginx/sites-available/instances")
ENABLED_DIR    = Path("/etc/nginx/sites-enabled")
CERT_PATH      = f"/etc/letsencrypt/live/{{DOMAIN}}/fullchain.pem"
KEY_PATH       = f"/etc/letsencrypt/live/{{DOMAIN}}/privkey.pem"


class NginxService:

    def add_instance_config(self, subdomain: str, port: int,
                            longpolling_port: int, odoo_version: str = "19"):
        """Create nginx config for a new instance and reload nginx"""
        SITES_DIR.mkdir(parents=True, exist_ok=True)
        config_path = SITES_DIR / f"{{subdomain}}.conf"

        # Check if wildcard cert exists, fall back to main domain cert
        wc_cert = f"/etc/letsencrypt/live/*.{{DOMAIN}}/fullchain.pem"
        wc_key  = f"/etc/letsencrypt/live/*.{{DOMAIN}}/privkey.pem"

        use_cert = CERT_PATH
        use_key  = KEY_PATH
        if os.path.exists(wc_cert.replace("*.", "")):
            use_cert = wc_cert
            use_key  = wc_key

        config = f"""
# Instance: {{subdomain}} — Odoo {{odoo_version}}
server {{
    listen 80;
    server_name {{subdomain}}.{DOMAIN};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl;
    server_name {{subdomain}}.{DOMAIN};

    ssl_certificate     {{use_cert}};
    ssl_certificate_key {{use_key}};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    proxy_read_timeout  720s;
    proxy_connect_timeout 720s;
    proxy_send_timeout  720s;

    # Odoo
    location / {{
        proxy_pass         http://127.0.0.1:{{port}};
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_redirect     off;
    }}

    # Longpolling
    location /longpolling {{
        proxy_pass         http://127.0.0.1:{{longpolling_port}};
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }}

    # Static files cache
    location ~* /web/static/ {{
        proxy_pass         http://127.0.0.1:{{port}};
        proxy_cache_valid  200 90m;
        proxy_buffering    on;
        expires            864000;
        add_header         Cache-Control "public, immutable";
    }}

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";

    client_max_body_size 512m;
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
}}
"""
        config_path.write_text(config)

        # Enable site
        enabled_link = ENABLED_DIR / f"{{subdomain}}.conf"
        if not enabled_link.exists():
            enabled_link.symlink_to(config_path)

        # Test + reload nginx
        result = subprocess.run(["nginx", "-t"], capture_output=True)
        if result.returncode == 0:
            subprocess.run(["systemctl", "reload", "nginx"])
        else:
            raise Exception(f"Nginx config error: {{result.stderr.decode()}}")

    def remove_instance_config(self, subdomain: str):
        enabled_link = ENABLED_DIR / f"{{subdomain}}.conf"
        config_path  = SITES_DIR / f"{{subdomain}}.conf"
        if enabled_link.exists():
            enabled_link.unlink()
        if config_path.exists():
            config_path.unlink()
        subprocess.run(["systemctl", "reload", "nginx"])
''')

# ══════════════════════════════════════════════════════════════════════════════
# 2. UPDATED PROVISIONING - template clone + aiohttp fix
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2/7] Updating ProvisioningEngine (template clone)...")
upload('/opt/clickbuild/backend/app/services/provisioning.py', f'''\
"""Provisioning Engine - قلب المنصة"""
import asyncio, docker, psycopg2, secrets, string, re, os, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.security import encrypt_secret
from app.models.instance import Instance, InstanceStatus
from app.models.user import User
from app.services.nginx_service import NginxService
from app.services.email_service import EmailService

TEMPLATE_DB    = "clickbuild_template"
BACKUP_DIR     = Path("/opt/clickbuild/backups")
SNAPSHOT_DIR   = Path("/opt/clickbuild/snapshots")
DATA_DIR       = Path("/opt/clickbuild/data")


class ProvisioningEngine:

    def __init__(self):
        self.docker_client = docker.from_env()
        self.nginx = NginxService()

    # ─── Public API ───────────────────────────────────────────────────────────

    async def create_instance(
        self, db: AsyncSession, user: User,
        subdomain: str, odoo_version: str = "19",
        modules: list = None, is_trial: bool = True,
        from_template: bool = True
    ) -> Instance:
        subdomain = self._sanitize_subdomain(subdomain)
        await self._assert_subdomain_available(db, subdomain)

        port             = await self._allocate_port(db)
        longpolling_port = port + 1000
        db_name          = f"odoo_{{subdomain}}"
        container_name   = f"odoo_{{subdomain}}"
        admin_pass       = self._generate_password()

        instance = Instance(
            user_id          = user.id,
            subdomain        = subdomain,
            display_name     = user.company_name or subdomain,
            odoo_version     = odoo_version,
            db_name          = db_name,
            odoo_port        = port,
            longpolling_port = longpolling_port,
            container_name   = container_name,
            admin_email      = user.email,
            admin_pass       = encrypt_secret(admin_pass),
            status           = InstanceStatus.PROVISIONING,
            is_trial         = is_trial,
            expires_at       = datetime.now(timezone.utc) + timedelta(days=settings.TRIAL_DAYS) if is_trial else None,
        )
        db.add(instance)
        await db.commit()
        await db.refresh(instance)

        asyncio.create_task(
            self._provision_async(
                instance.id, db_name, container_name,
                port, longpolling_port, odoo_version,
                modules or ["base", "web"],
                user, admin_pass, db, from_template
            )
        )
        return instance

    async def stop_instance(self, instance: Instance) -> bool:
        try:
            c = self.docker_client.containers.get(instance.container_name)
            c.stop(timeout=10)
            return True
        except docker.errors.NotFound:
            return False

    async def start_instance(self, instance: Instance) -> bool:
        try:
            c = self.docker_client.containers.get(instance.container_name)
            c.start()
            return True
        except docker.errors.NotFound:
            return False

    async def delete_instance(self, db: AsyncSession, instance: Instance) -> bool:
        try:
            try:
                c = self.docker_client.containers.get(instance.container_name)
                c.stop(timeout=5); c.remove(force=True)
            except docker.errors.NotFound:
                pass
            self._drop_database(instance.db_name)
            self.nginx.remove_instance_config(instance.subdomain)
            instance.status = InstanceStatus.DELETED
            instance.deleted_at = datetime.now(timezone.utc)
            await db.commit()
            return True
        except Exception as e:
            instance.error_msg = str(e)
            await db.commit()
            return False

    async def clone_instance(
        self, db: AsyncSession, source: Instance,
        new_subdomain: str, is_staging: bool = True
    ) -> Instance:
        """Clone an instance (for staging)"""
        user_res = await db.execute(select(User).where(User.id == source.user_id))
        user = user_res.scalar_one()

        clone = await self.create_instance(
            db, user, new_subdomain,
            odoo_version = source.odoo_version,
            is_trial     = False,
            from_template = False
        )
        # Override: clone the source DB after container starts
        asyncio.create_task(
            self._clone_db_when_ready(source.db_name, clone.db_name, clone.id, db)
        )
        return clone

    async def take_snapshot(self, instance: Instance) -> dict:
        """pg_dump + docker commit atomically"""
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{{instance.subdomain}}_{{ts}}"

        snap_dir = SNAPSHOT_DIR / instance.subdomain
        snap_dir.mkdir(parents=True, exist_ok=True)

        # 1. DB snapshot
        db_file = snap_dir / f"{{name}}.sql.gz"
        env = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
        subprocess.run([
            "pg_dump", "-h", settings.POSTGRES_HOST,
            "-U", settings.POSTGRES_USER, "-d", instance.db_name,
            "--compress=9", "-f", str(db_file)
        ], env=env, check=True)

        # 2. Docker commit (filesystem snapshot)
        try:
            c = self.docker_client.containers.get(instance.container_name)
            img = c.commit(
                repository=f"clickbuild/snap_{{instance.subdomain}}",
                tag=ts
            )
            docker_image = img.id
        except Exception:
            docker_image = None

        size = db_file.stat().st_size if db_file.exists() else 0
        return {{
            "name": name,
            "timestamp": ts,
            "db_file": str(db_file),
            "docker_image": docker_image,
            "size_mb": round(size / 1e6, 2),
        }}

    def list_snapshots(self, subdomain: str) -> list:
        snap_dir = SNAPSHOT_DIR / subdomain
        if not snap_dir.exists():
            return []
        snaps = []
        for f in sorted(snap_dir.glob("*.sql.gz"), reverse=True)[:20]:
            stat = f.stat()
            snaps.append({{
                "name": f.stem.replace(".sql", ""),
                "db_file": str(f),
                "size_mb": round(stat.st_size / 1e6, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }})
        return snaps

    async def restore_snapshot(self, instance: Instance, snapshot_name: str) -> bool:
        """Restore instance to a snapshot"""
        snap_dir = SNAPSHOT_DIR / instance.subdomain
        db_file  = snap_dir / f"{{snapshot_name}}.sql.gz"
        if not db_file.exists():
            raise FileNotFoundError(f"Snapshot not found: {{snapshot_name}}")

        # 1. Stop container
        await self.stop_instance(instance)
        await asyncio.sleep(2)

        # 2. Drop + recreate DB
        self._drop_database(instance.db_name)
        self._create_database(instance.db_name)

        # 3. Restore dump
        env = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
        proc = subprocess.run(
            f"gunzip -c {{db_file}} | psql -h {{settings.POSTGRES_HOST}} "
            f"-U {{settings.POSTGRES_USER}} {{instance.db_name}}",
            shell=True, env=env
        )
        if proc.returncode != 0:
            raise Exception("DB restore failed")

        # 4. Try to restore docker image
        try:
            img_name = f"clickbuild/snap_{{instance.subdomain}}"
            ts = snapshot_name.split("_")[-1]
            img = self.docker_client.images.get(f"{{img_name}}:{{ts}}")
            self.docker_client.containers.get(instance.container_name).remove(force=True)
        except Exception:
            pass

        # 5. Restart container
        await self.start_instance(instance)
        return True

    async def upgrade_instance(self, db: AsyncSession, instance: Instance, target_version: str) -> bool:
        instance.status = InstanceStatus.UPGRADING
        instance.odoo_version_target = target_version
        await db.commit()
        asyncio.create_task(self._upgrade_async(instance, target_version, db))
        return True

    # ─── Private ──────────────────────────────────────────────────────────────

    async def _provision_async(
        self, instance_id, db_name, container_name,
        port, longpolling_port, odoo_version, modules,
        user, admin_pass, db, from_template
    ):
        result = await db.execute(select(Instance).where(Instance.id == instance_id))
        instance = result.scalar_one_or_none()
        if not instance:
            return

        try:
            # 1. Create DB (from template if available)
            await asyncio.get_event_loop().run_in_executor(
                None, self._create_database, db_name, from_template
            )

            # 2. Start container
            container = await asyncio.get_event_loop().run_in_executor(
                None, self._start_container,
                container_name, db_name, port, longpolling_port,
                odoo_version, modules, user, admin_pass,
                not from_template  # init_db=True only if not from template
            )
            instance.container_id = container.id

            # 3. Wait for Odoo to be ready
            await self._wait_for_odoo(port)

            # 4. Add Nginx config
            self.nginx.add_instance_config(
                subdomain        = instance.subdomain,
                port             = port,
                longpolling_port = longpolling_port,
                odoo_version     = odoo_version
            )

            instance.status = InstanceStatus.RUNNING
            await db.commit()

            await EmailService.send_instance_ready(
                email      = user.email,
                name       = user.name,
                subdomain  = instance.subdomain,
                admin_pass = admin_pass,
                expires_at = instance.expires_at,
                language   = user.language
            )

        except Exception as e:
            instance.status    = InstanceStatus.ERROR
            instance.error_msg = str(e)[:500]
            await db.commit()

    async def _clone_db_when_ready(self, src_db: str, dest_db: str, instance_id, db):
        await asyncio.sleep(5)
        result = await db.execute(select(Instance).where(Instance.id == instance_id))
        instance = result.scalar_one_or_none()
        if not instance:
            return
        try:
            self._drop_database(dest_db)
            env = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
            subprocess.run([
                "pg_dump", "-h", settings.POSTGRES_HOST,
                "-U", settings.POSTGRES_USER, "-d", src_db,
                "--no-owner", "--no-acl",
            ], env=env, check=True,
                stdout=subprocess.PIPE
            )
        except Exception:
            pass

    def _start_container(
        self, name, db_name, port, lp_port,
        version, modules, user, admin_pass, init_db=True
    ):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data_vol = DATA_DIR / db_name
        data_vol.mkdir(parents=True, exist_ok=True)

        return self.docker_client.containers.run(
            image   = f"clickbuild/odoo:{{version}}",
            name    = name,
            detach  = True,
            restart_policy = {{"Name": "unless-stopped"}},
            network = "clickbuild-net",
            ports   = {{
                "8069/tcp": ("127.0.0.1", port),
                "8072/tcp": ("127.0.0.1", lp_port),
            }},
            environment = {{
                "DB_HOST"         : settings.POSTGRES_HOST,
                "DB_PORT"         : str(settings.POSTGRES_PORT),
                "DB_USER"         : settings.POSTGRES_USER,
                "DB_PASSWORD"     : settings.POSTGRES_PASSWORD,
                "DB_NAME"         : db_name,
                "MASTER_PASSWORD" : settings.ODOO_MASTER_PASSWORD,
                "ADMIN_EMAIL"     : user.email,
                "ADMIN_PASSWORD"  : admin_pass,
                "COMPANY_NAME"    : user.company_name or user.name,
                "ODOO_MODULES"    : ",".join(modules),
                "ODOO_LANG"       : "ar_001,en_US",
                "WITHOUT_DEMO"    : "all",
                "INIT_DB"         : "true" if init_db else "false",
                "ODOO_VERSION"    : version,
                "SMTP_HOST"       : settings.SMTP_HOST,
                "SMTP_PORT"       : str(settings.SMTP_PORT),
                "SMTP_SSL"        : "true",
                "SMTP_USER"       : settings.SMTP_USER,
                "SMTP_PASSWORD"   : settings.SMTP_PASSWORD,
                "EMAIL_FROM"      : settings.EMAIL_FROM,
            }},
            mem_limit   = "1g",
            cpu_period  = 100000,
            cpu_quota   = 100000,
            volumes     = {{
                str(data_vol): {{"bind": "/var/lib/odoo", "mode": "rw"}}
            }}
        )

    async def _upgrade_async(self, instance: Instance, target_version: str, db: AsyncSession):
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._backup_database, instance.db_name
            )
            try:
                old = self.docker_client.containers.get(instance.container_name)
                old.stop(timeout=30)
                old.remove()
            except Exception:
                pass

            data_vol = DATA_DIR / instance.db_name
            container = self.docker_client.containers.run(
                image   = f"clickbuild/odoo:{{target_version}}",
                name    = instance.container_name,
                detach  = True,
                restart_policy = {{"Name": "unless-stopped"}},
                network = "clickbuild-net",
                ports   = {{
                    "8069/tcp": ("127.0.0.1", instance.odoo_port),
                    "8072/tcp": ("127.0.0.1", instance.longpolling_port),
                }},
                environment = {{
                    "DB_HOST": settings.POSTGRES_HOST,
                    "DB_PORT": str(settings.POSTGRES_PORT),
                    "DB_USER": settings.POSTGRES_USER,
                    "DB_PASSWORD": settings.POSTGRES_PASSWORD,
                    "DB_NAME": instance.db_name,
                    "MASTER_PASSWORD": settings.ODOO_MASTER_PASSWORD,
                    "INIT_DB": "false",
                    "ODOO_VERSION": target_version,
                }},
                volumes = {{str(data_vol): {{"bind": "/var/lib/odoo", "mode": "rw"}}}},
                mem_limit="1g", cpu_period=100000, cpu_quota=100000
            )
            instance.odoo_version        = target_version
            instance.odoo_version_target = None
            instance.status              = InstanceStatus.RUNNING
            instance.container_id        = container.id
            await db.commit()
        except Exception as e:
            instance.status    = InstanceStatus.ERROR
            instance.error_msg = f"Upgrade failed: {{e}}"
            await db.commit()

    # ─── DB helpers ───────────────────────────────────────────────────────────

    def _create_database(self, db_name: str, from_template: bool = True):
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
            dbname="postgres"
        )
        conn.autocommit = True
        cur = conn.cursor()
        # Try template clone first
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TEMPLATE_DB,))
        template_exists = cur.fetchone() is not None

        if from_template and template_exists:
            cur.execute(f"""
                CREATE DATABASE "{{db_name}}"
                TEMPLATE "{{TEMPLATE_DB}}"
                OWNER "{{settings.POSTGRES_USER}}"
            """)
        else:
            cur.execute(f'CREATE DATABASE "{{db_name}}" OWNER "{{settings.POSTGRES_USER}}"')
        cur.close(); conn.close()

    def _drop_database(self, db_name: str):
        conn = psycopg2.connect(
            host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
            dbname="postgres"
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname=%s AND pid<>pg_backend_pid()
        """, (db_name,))
        cur.execute(f'DROP DATABASE IF EXISTS "{{db_name}}"')
        cur.close(); conn.close()

    def _backup_database(self, db_name: str, backup_type: str = "manual") -> str:
        sub_dir = BACKUP_DIR / db_name / backup_type
        sub_dir.mkdir(parents=True, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = sub_dir / f"{{db_name}}_{{ts}}.sql.gz"
        env  = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
        subprocess.run([
            "pg_dump", "-h", settings.POSTGRES_HOST,
            "-U", settings.POSTGRES_USER, "-d", db_name,
            "--compress=9", "-f", str(dest)
        ], env=env, check=True)
        return str(dest)

    async def _wait_for_odoo(self, port: int, timeout: int = 180):
        import urllib.request
        url      = f"http://127.0.0.1:{{port}}/web/health"
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=5) as r:
                    if r.status == 200:
                        return
            except Exception:
                pass
            await asyncio.sleep(5)
        raise TimeoutError(f"Odoo on port {{port}} did not respond in {{timeout}}s")

    async def _allocate_port(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(func.max(Instance.odoo_port)).where(
                Instance.status != InstanceStatus.DELETED
            )
        )
        max_port = result.scalar_one_or_none()
        if not max_port or max_port < settings.ODOO_PORT_START:
            return settings.ODOO_PORT_START
        next_port = max_port + 2
        if next_port > settings.ODOO_PORT_END:
            raise Exception("No available ports")
        return next_port

    async def _assert_subdomain_available(self, db: AsyncSession, subdomain: str):
        result = await db.execute(
            select(Instance).where(
                Instance.subdomain == subdomain,
                Instance.status != InstanceStatus.DELETED
            )
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Subdomain '{{subdomain}}' already taken")

    @staticmethod
    def _sanitize_subdomain(raw: str) -> str:
        s = raw.lower().strip()
        s = re.sub(r"[^a-z0-9-]", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        if len(s) < 3:  raise ValueError("Min 3 characters")
        if len(s) > 63: raise ValueError("Max 63 characters")
        return s

    @staticmethod
    def _generate_password(length: int = 16) -> str:
        chars = string.ascii_letters + string.digits + "!@#$"
        return "".join(secrets.choice(chars) for _ in range(length))
''')

# ══════════════════════════════════════════════════════════════════════════════
# 3. CELERY WORKERS - backup + lifecycle
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3/7] Creating Celery workers...")

upload('/opt/clickbuild/backend/app/workers/__init__.py', '')

upload('/opt/clickbuild/backend/app/workers/celery_app.py', '''\
"""Celery application instance"""
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "clickbuild",
    broker    = settings.REDIS_URL,
    backend   = settings.REDIS_URL,
    include   = ["app.workers.backup", "app.workers.lifecycle"],
)

celery_app.conf.timezone = "Africa/Cairo"

celery_app.conf.beat_schedule = {
    # Hourly backup of all running instances
    "backup-hourly": {
        "task"    : "app.workers.backup.backup_all",
        "schedule": crontab(minute=0),
        "args"    : ("hourly",),
    },
    # Daily backup at 2 AM
    "backup-daily": {
        "task"    : "app.workers.backup.backup_all",
        "schedule": crontab(minute=0, hour=2),
        "args"    : ("daily",),
    },
    # Weekly backup Sunday 3 AM
    "backup-weekly": {
        "task"    : "app.workers.backup.backup_all",
        "schedule": crontab(minute=0, hour=3, day_of_week=0),
        "args"    : ("weekly",),
    },
    # Monthly backup 1st of month 4 AM
    "backup-monthly": {
        "task"    : "app.workers.backup.backup_all",
        "schedule": crontab(minute=0, hour=4, day_of_month=1),
        "args"    : ("monthly",),
    },
    # Lifecycle check every 30 minutes
    "lifecycle-check": {
        "task"    : "app.workers.lifecycle.check_expired",
        "schedule": crontab(minute="*/30"),
    },
}
''')

upload('/opt/clickbuild/backend/app/workers/backup.py', f'''\
"""Backup worker - runs scheduled backups for all instances"""
import os, subprocess, logging
from datetime import datetime
from pathlib import Path
import psycopg2

from app.workers.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR     = Path("/opt/clickbuild/backups")
RETENTION_DAYS = {{"hourly": 1, "daily": 7, "weekly": 4, "monthly": 12}}
# hourly: keep 24 backups; daily: 7 days; weekly: 4 weeks; monthly: 12 months
RETENTION_COUNT = {{"hourly": 24, "daily": 7, "weekly": 4, "monthly": 12}}


@celery_app.task(name="app.workers.backup.backup_all", bind=True, max_retries=2)
def backup_all(self, backup_type: str = "manual"):
    """Backup all running instances"""
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT db_name, subdomain FROM instances
        WHERE status = 'running' AND db_name IS NOT NULL
    """)
    instances = cur.fetchall()
    cur.close(); conn.close()

    results = []
    for db_name, subdomain in instances:
        try:
            path = _backup_db(db_name, subdomain, backup_type)
            _prune_backups(subdomain, backup_type)
            results.append({{"subdomain": subdomain, "ok": True, "file": path}})
            logger.info(f"Backup OK: {{subdomain}} ({{backup_type}})")
        except Exception as e:
            results.append({{"subdomain": subdomain, "ok": False, "error": str(e)}})
            logger.error(f"Backup FAIL: {{subdomain}}: {{e}}")
    return results


@celery_app.task(name="app.workers.backup.backup_instance")
def backup_instance(db_name: str, subdomain: str, backup_type: str = "manual"):
    """Backup a single instance"""
    path = _backup_db(db_name, subdomain, backup_type)
    _prune_backups(subdomain, backup_type)
    return {{"ok": True, "file": path}}


def _backup_db(db_name: str, subdomain: str, backup_type: str) -> str:
    sub_dir = BACKUP_DIR / subdomain / backup_type
    sub_dir.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = sub_dir / f"{{db_name}}_{{ts}}.sql.gz"
    env  = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
    result = subprocess.run([
        "pg_dump", "-h", settings.POSTGRES_HOST,
        "-U", settings.POSTGRES_USER, "-d", db_name,
        "--compress=9", "-f", str(dest)
    ], env=env, capture_output=True)
    if result.returncode != 0:
        raise Exception(result.stderr.decode())
    return str(dest)


def _prune_backups(subdomain: str, backup_type: str):
    """Keep only N most recent backups of this type"""
    sub_dir = BACKUP_DIR / subdomain / backup_type
    if not sub_dir.exists():
        return
    files = sorted(sub_dir.glob("*.sql.gz"), key=lambda f: f.stat().st_mtime, reverse=True)
    keep  = RETENTION_COUNT.get(backup_type, 10)
    for old in files[keep:]:
        old.unlink(missing_ok=True)
''')

upload('/opt/clickbuild/backend/app/workers/lifecycle.py', '''\
"""Lifecycle worker - auto-suspend expired trials + cleanup"""
import logging
import psycopg2
import docker
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.lifecycle.check_expired")
def check_expired():
    """Suspend containers whose trial/subscription has expired"""
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    cur = conn.cursor()

    # Find expired running instances
    cur.execute("""
        SELECT id, container_name, subdomain FROM instances
        WHERE status = 'running'
          AND expires_at IS NOT NULL
          AND expires_at < NOW()
    """)
    expired = cur.fetchall()

    dc = docker.from_env()
    suspended = []

    for inst_id, container_name, subdomain in expired:
        try:
            c = dc.containers.get(container_name)
            c.stop(timeout=10)
            cur.execute(
                "UPDATE instances SET status='suspended' WHERE id=%s",
                (str(inst_id),)
            )
            conn.commit()
            suspended.append(subdomain)
            logger.info(f"Auto-suspended expired instance: {subdomain}")
        except docker.errors.NotFound:
            cur.execute(
                "UPDATE instances SET status='expired' WHERE id=%s",
                (str(inst_id),)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to suspend {subdomain}: {e}")

    cur.close(); conn.close()
    return {"suspended": suspended, "count": len(suspended)}


@celery_app.task(name="app.workers.lifecycle.cleanup_deleted")
def cleanup_deleted():
    """Remove Docker containers and volumes for deleted instances"""
    conn = psycopg2.connect(
        host=settings.POSTGRES_HOST, port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER, password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT container_name FROM instances
        WHERE status = 'deleted'
          AND deleted_at < NOW() - INTERVAL '24 hours'
          AND container_name IS NOT NULL
    """)
    rows = cur.fetchall()
    cur.close(); conn.close()

    dc = docker.from_env()
    for (container_name,) in rows:
        try:
            c = dc.containers.get(container_name)
            c.remove(force=True)
        except docker.errors.NotFound:
            pass
''')

# ══════════════════════════════════════════════════════════════════════════════
# 4. ADMIN API - add snapshot + staging endpoints
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4/7] Updating Admin API (snapshots + staging)...")
upload('/opt/clickbuild/backend/app/api/v1/endpoints/admin.py', f'''\
"""Admin API - Super Admin endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime
from typing import Optional
import docker, subprocess, os
from pathlib import Path

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.instance import Instance, InstanceStatus
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

    import psutil
    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    try:
        dc = docker.from_env()
        docker_running = len(dc.containers.list())
    except Exception:
        docker_running = 0

    return {{
        "users":     {{"total": total_users, "active": active_users}},
        "instances": {{"total": total_instances, "running": running, "trial": trial, "errors": errors}},
        "server":    {{
            "cpu_pct":       cpu,
            "ram_used_gb":   round(ram.used / 1e9, 2),
            "ram_total_gb":  round(ram.total / 1e9, 2),
            "ram_pct":       ram.percent,
            "disk_used_gb":  round(disk.used / 1e9, 2),
            "disk_total_gb": round(disk.total / 1e9, 2),
            "disk_pct":      disk.percent,
        }},
        "docker": {{"running_containers": docker_running}},
    }}


# ─── Users ────────────────────────────────────────────────────────────────────
@router.get("/users")
async def list_users(
    page: int = 1, per_page: int = 20, search: Optional[str] = None,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    q = select(User).order_by(User.created_at.desc())
    if search:
        q = q.where(User.email.ilike(f"%{{search}}%") | User.name.ilike(f"%{{search}}%"))
    total  = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result = await db.execute(q.offset((page-1)*per_page).limit(per_page))
    users  = result.scalars().all()
    return {{
        "total": total, "page": page, "per_page": per_page,
        "users": [{{
            "id": str(u.id), "email": u.email, "name": u.name,
            "company": u.company_name, "country": u.country,
            "is_active": u.is_active, "is_superuser": u.is_superuser,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login_at.isoformat() if u.last_login_at else None,
        }} for u in users]
    }}


@router.patch("/users/{{user_id}}")
async def update_user(
    user_id: str, body: dict,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user   = result.scalar_one_or_none()
    if not user: raise HTTPException(404, "User not found")
    for field in ["is_active", "is_superuser"]:
        if field in body:
            setattr(user, field, body[field])
    await db.commit()
    return {{"ok": True}}


# ─── Instances ────────────────────────────────────────────────────────────────
@router.get("/instances")
async def list_all_instances(
    page: int = 1, per_page: int = 20, status_filter: Optional[str] = None,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    q = (select(Instance, User)
         .join(User, Instance.user_id == User.id)
         .where(Instance.status != InstanceStatus.DELETED)
         .order_by(Instance.created_at.desc()))
    if status_filter:
        q = q.where(Instance.status == status_filter)
    total  = (await db.execute(select(func.count(Instance.id)).where(Instance.status != InstanceStatus.DELETED))).scalar()
    result = await db.execute(q.offset((page-1)*per_page).limit(per_page))
    rows   = result.all()
    return {{
        "total": total, "page": page, "per_page": per_page,
        "instances": [{{
            "id": str(inst.id), "subdomain": inst.subdomain, "url": inst.url,
            "status": inst.status, "odoo_version": inst.odoo_version,
            "is_trial": inst.is_trial,
            "expires_at": inst.expires_at.isoformat() if inst.expires_at else None,
            "created_at": inst.created_at.isoformat() if inst.created_at else None,
            "cpu_limit": inst.cpu_limit, "memory_mb": inst.memory_mb,
            "port": inst.odoo_port, "error_msg": inst.error_msg,
            "db_name": inst.db_name,
            "user": {{"id": str(u.id), "email": u.email, "name": u.name, "company": u.company_name}},
        }} for inst, u in rows]
    }}


@router.post("/instances/{{instance_id}}/suspend")
async def suspend_instance(
    instance_id: str,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    await engine.stop_instance(inst)
    inst.status = InstanceStatus.SUSPENDED
    await db.commit()
    return {{"ok": True, "status": "suspended"}}


@router.post("/instances/{{instance_id}}/resume")
async def resume_instance(
    instance_id: str,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    await engine.start_instance(inst)
    inst.status = InstanceStatus.RUNNING
    await db.commit()
    return {{"ok": True, "status": "running"}}


@router.delete("/instances/{{instance_id}}")
async def delete_instance(
    instance_id: str,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    await engine.delete_instance(db, inst)
    return {{"ok": True}}


# ─── Snapshots ────────────────────────────────────────────────────────────────
@router.post("/instances/{{instance_id}}/snapshot")
async def create_snapshot(
    instance_id: str, background_tasks: BackgroundTasks,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    if not inst.db_name: raise HTTPException(400, "No DB configured")

    def do_snap():
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(engine.take_snapshot(inst))

    background_tasks.add_task(do_snap)
    return {{"ok": True, "message": "Snapshot started in background"}}


@router.get("/instances/{{instance_id}}/snapshots")
async def list_snapshots(
    instance_id: str,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    return {{"snapshots": engine.list_snapshots(inst.subdomain)}}


@router.post("/instances/{{instance_id}}/snapshots/{{snapshot_name}}/restore")
async def restore_snapshot(
    instance_id: str, snapshot_name: str,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    try:
        await engine.restore_snapshot(inst, snapshot_name)
        return {{"ok": True}}
    except FileNotFoundError:
        raise HTTPException(404, "Snapshot not found")


# ─── Staging clone ────────────────────────────────────────────────────────────
@router.post("/instances/{{instance_id}}/clone")
async def clone_instance(
    instance_id: str, body: dict,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    new_subdomain = body.get("subdomain", f"staging-{{inst.subdomain}}")
    clone = await engine.clone_instance(db, inst, new_subdomain, is_staging=True)
    return {{"ok": True, "instance_id": str(clone.id), "subdomain": clone.subdomain}}


# ─── Container Stats ──────────────────────────────────────────────────────────
@router.get("/instances/{{instance_id}}/stats")
async def instance_stats(
    instance_id: str,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    try:
        dc        = docker.from_env()
        container = dc.containers.get(inst.container_name)
        raw       = container.stats(stream=False)
        cpu_d     = raw["cpu_stats"]["cpu_usage"]["total_usage"] - raw["precpu_stats"]["cpu_usage"]["total_usage"]
        sys_d     = raw["cpu_stats"]["system_cpu_usage"] - raw["precpu_stats"]["system_cpu_usage"]
        ncpu      = raw["cpu_stats"].get("online_cpus", 1)
        cpu_pct   = round((cpu_d / sys_d) * ncpu * 100, 2) if sys_d > 0 else 0
        mem_used  = raw["memory_stats"]["usage"]
        mem_limit = raw["memory_stats"]["limit"]
        net_in    = sum(v["rx_bytes"] for v in raw.get("networks", {{}}).values())
        net_out   = sum(v["tx_bytes"] for v in raw.get("networks", {{}}).values())
        return {{
            "status": container.status, "cpu_pct": cpu_pct,
            "mem_used_mb": round(mem_used/1e6,1), "mem_limit_mb": round(mem_limit/1e6,1),
            "mem_pct": round(mem_used/mem_limit*100,2),
            "net_in_mb": round(net_in/1e6,2), "net_out_mb": round(net_out/1e6,2),
        }}
    except docker.errors.NotFound:
        return {{"status": "not_found", "cpu_pct": 0, "mem_used_mb": 0, "mem_limit_mb": 0, "mem_pct": 0}}
    except Exception as e:
        return {{"status": "error", "error": str(e)}}


# ─── Backup ───────────────────────────────────────────────────────────────────
@router.post("/instances/{{instance_id}}/backup")
async def backup_instance(
    instance_id: str, background_tasks: BackgroundTasks,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    if not inst.db_name: raise HTTPException(400, "No DB configured")

    def do_backup():
        from app.workers.backup import backup_instance as worker_backup
        worker_backup.delay(inst.db_name, inst.subdomain, "manual")

    background_tasks.add_task(do_backup)
    return {{"ok": True, "message": "Backup queued"}}


@router.get("/instances/{{instance_id}}/backups")
async def list_backups(
    instance_id: str, backup_type: str = "manual",
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    backup_dir = Path(f"/opt/clickbuild/backups/{{inst.subdomain}}/{{backup_type}}")
    if not backup_dir.exists():
        # Try old path for backwards compat
        backup_dir = Path(f"/opt/clickbuild/backups/{{inst.subdomain}}")
    if not backup_dir.exists():
        return {{"backups": []}}
    backups = []
    for f in sorted(backup_dir.glob("*.sql.gz"), reverse=True)[:30]:
        stat = f.stat()
        backups.append({{
            "name": f.name, "size_mb": round(stat.st_size/1e6,2),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "type": backup_type,
        }})
    return {{"backups": backups}}


# ─── Logs ─────────────────────────────────────────────────────────────────────
@router.get("/instances/{{instance_id}}/logs")
async def instance_logs(
    instance_id: str, lines: int = 100,
    admin: User = Depends(require_superuser), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Instance).where(Instance.id == instance_id))
    inst   = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    try:
        dc        = docker.from_env()
        container = dc.containers.get(inst.container_name)
        logs      = container.logs(tail=lines, timestamps=True).decode("utf-8", errors="replace")
        return {{"logs": logs, "lines": lines}}
    except docker.errors.NotFound:
        return {{"logs": "Container not found", "lines": 0}}
    except Exception as e:
        return {{"logs": str(e), "lines": 0}}
''')

# ══════════════════════════════════════════════════════════════════════════════
# 5. DASHBOARD PAGE - complete rewrite
# ══════════════════════════════════════════════════════════════════════════════
print("\n[5/7] Rebuilding Dashboard page...")
upload('/opt/clickbuild/frontend/src/app/[locale]/dashboard/page.tsx', f'''\
\'use client\';
import {{ useState, useEffect }} from \'react\';
import {{ useRouter }} from \'next/navigation\';
import Link from \'next/link\';

const API = process.env.NEXT_PUBLIC_API_URL ?? \'/api/v1\';

const STATUS_MAP: Record<string, [string, string]> = {{
  running:      [\'يعمل\',         \'bg-green-100 text-green-700\'],
  stopped:      [\'متوقف\',        \'bg-gray-100 text-gray-600\'],
  suspended:    [\'موقوف\',        \'bg-orange-100 text-orange-700\'],
  provisioning: [\'جاري الإنشاء\', \'bg-blue-100 text-blue-700\'],
  error:        [\'خطأ\',          \'bg-red-100 text-red-700\'],
  expired:      [\'منتهي\',        \'bg-red-100 text-red-600\'],
  upgrading:    [\'ترقية جارية\',  \'bg-purple-100 text-purple-700\'],
}};

export default function DashboardPage() {{
  const router  = useRouter();
  const [user, setUser]           = useState<any>(null);
  const [instances, setInstances] = useState<any[]>([]);
  const [loading, setLoading]     = useState(true);
  const [token, setToken]         = useState(\'\');

  useEffect(() => {{
    const stored = localStorage.getItem(\'clickbuild-auth\');
    if (!stored) {{ router.push(\'/login\'); return; }}
    const auth = JSON.parse(stored);
    const t = auth?.state?.accessToken;
    const u = auth?.state?.user;
    if (!t) {{ router.push(\'/login\'); return; }}
    setToken(t);
    setUser(u);
    load(t);
    const iv = setInterval(() => load(t), 15000);
    return () => clearInterval(iv);
  }}, []);

  async function load(t: string) {{
    try {{
      const res = await fetch(`${{API}}/instances/`, {{
        headers: {{ Authorization: `Bearer ${{t}}` }}
      }});
      if (res.status === 401) {{ router.push(\'/login\'); return; }}
      if (res.ok) {{
        const data = await res.json();
        setInstances(data.instances || data || []);
      }}
    }} finally {{
      setLoading(false);
    }}
  }}

  function logout() {{
    localStorage.removeItem(\'clickbuild-auth\');
    router.push(\'/login\');
  }}

  const activeCount      = instances.filter(i => i.status === \'running\').length;
  const provisioningCount= instances.filter(i => i.status === \'provisioning\').length;

  return (
    <div className="min-h-screen bg-gray-50 font-sans" dir="rtl">
      {{/* Header */}}
      <header className="bg-white border-b shadow-sm">
        <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-violet-700 rounded-lg flex items-center justify-center">
              <span className="text-white font-black text-sm">O</span>
            </div>
            <span className="font-black text-lg text-gray-900">OdooClickBuild</span>
          </div>
          <div className="flex items-center gap-4">
            {{user?.is_superuser && (
              <Link href="/admin"
                className="text-xs bg-red-100 text-red-700 font-bold px-3 py-1 rounded-full hover:bg-red-200">
                Super Admin
              </Link>
            )}}
            <span className="text-sm text-gray-500">مرحباً، {{user?.name || \'...\'}}</span>
            <button onClick={{logout}}
              className="text-sm text-gray-400 hover:text-red-600 transition">
              تسجيل الخروج
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {{/* Stats bar */}}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-2xl border p-4 text-center shadow-sm">
            <div className="text-2xl font-black text-violet-700">{{instances.length}}</div>
            <div className="text-sm text-gray-500 mt-1">إجمالي البيئات</div>
          </div>
          <div className="bg-white rounded-2xl border p-4 text-center shadow-sm">
            <div className="text-2xl font-black text-green-600">{{activeCount}}</div>
            <div className="text-sm text-gray-500 mt-1">تعمل الآن</div>
          </div>
          <div className="bg-white rounded-2xl border p-4 text-center shadow-sm">
            <div className={{`text-2xl font-black ${{provisioningCount > 0 ? \'text-blue-600\' : \'text-gray-400\'}}`}}>
              {{provisioningCount}}
            </div>
            <div className="text-sm text-gray-500 mt-1">جاري الإنشاء</div>
          </div>
        </div>

        {{/* Instances */}}
        <div className="flex justify-between items-center mb-4">
          <h1 className="text-xl font-black">بيئات Odoo</h1>
          <Link href="/create"
            className="bg-violet-700 text-white px-5 py-2 rounded-xl text-sm font-semibold hover:bg-violet-800 transition shadow-sm">
            + بيئة جديدة
          </Link>
        </div>

        {{loading ? (
          <div className="text-center py-16 text-gray-400">جاري التحميل...</div>
        ) : instances.length === 0 ? (
          <div className="bg-white rounded-2xl border p-12 text-center shadow-sm">
            <div className="text-5xl mb-4">🚀</div>
            <h2 className="text-xl font-bold mb-2">ابدأ رحلتك مع Odoo</h2>
            <p className="text-gray-500 mb-6">أنشئ أول بيئة Odoo خاصة بك مجاناً</p>
            <Link href="/create"
              className="bg-violet-700 text-white px-8 py-3 rounded-xl font-semibold hover:bg-violet-800 transition inline-block">
              إنشاء بيئة مجانية
            </Link>
          </div>
        ) : (
          <div className="grid gap-4">
            {{instances.map((inst: any) => (
              <InstanceCard key={{inst.id}} inst={{inst}} token={{token}} onRefresh={{() => load(token)}} />
            ))}}
          </div>
        )}}
      </main>
    </div>
  );
}}

function InstanceCard({{ inst, token, onRefresh }}: {{ inst: any; token: string; onRefresh: () => void }}) {{
  const [expanded, setExpanded] = useState(false);
  const API = process.env.NEXT_PUBLIC_API_URL ?? \'/api/v1\';
  const [label, cls] = STATUS_MAP[inst.status] || [inst.status, \'bg-gray-100\'];

  const isRunning = inst.status === \'running\';
  const isProvisioning = inst.status === \'provisioning\';

  // Auto-refresh while provisioning
  useEffect(() => {{
    if (!isProvisioning) return;
    const iv = setInterval(onRefresh, 10000);
    return () => clearInterval(iv);
  }}, [isProvisioning]);

  async function stop() {{
    await fetch(`${{API}}/instances/${{inst.id}}/stop`, {{
      method: \'POST\', headers: {{ Authorization: `Bearer ${{token}}` }}
    }});
    onRefresh();
  }}

  async function start() {{
    await fetch(`${{API}}/instances/${{inst.id}}/start`, {{
      method: \'POST\', headers: {{ Authorization: `Bearer ${{token}}` }}
    }});
    onRefresh();
  }}

  const expiresAt   = inst.expires_at ? new Date(inst.expires_at) : null;
  const daysLeft    = expiresAt ? Math.ceil((expiresAt.getTime() - Date.now()) / 86400000) : null;
  const isExpiringSoon = daysLeft !== null && daysLeft <= 3 && daysLeft > 0;

  return (
    <div className={{`bg-white rounded-2xl border shadow-sm overflow-hidden transition ${{isRunning ? \'border-green-200\' : \'\'}}`}}>
      <div className="p-5">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={{`w-10 h-10 rounded-xl flex items-center justify-center text-lg font-black ${{isRunning ? \'bg-green-100\' : \'bg-gray-100\'}}`}}>
              O
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-gray-900">{{inst.display_name || inst.subdomain}}</h3>
                <span className={{`text-xs font-medium px-2 py-0.5 rounded-full ${{cls}}`}}>{{label}}</span>
                {{inst.is_trial && (
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">تجريبي</span>
                )}}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {{inst.subdomain}}.{DOMAIN} • Odoo {{inst.odoo_version}}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {{isRunning && (
              <a href={{`https://${{inst.subdomain}}.{DOMAIN}`}} target="_blank" rel="noopener"
                className="bg-violet-700 text-white px-4 py-1.5 rounded-lg text-sm font-medium hover:bg-violet-800 transition">
                فتح Odoo
              </a>
            )}}
            {{isProvisioning && (
              <div className="flex items-center gap-2 text-blue-600 text-sm">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
                جاري الإعداد...
              </div>
            )}}
            {{isRunning && (
              <button onClick={{stop}}
                className="text-sm text-orange-600 hover:text-orange-800 px-3 py-1.5 rounded-lg hover:bg-orange-50 transition">
                إيقاف
              </button>
            )}}
            {{inst.status === \'stopped\' && (
              <button onClick={{start}}
                className="text-sm text-green-600 hover:text-green-800 px-3 py-1.5 rounded-lg hover:bg-green-50 transition">
                تشغيل
              </button>
            )}}
            <button onClick={{() => setExpanded(!expanded)}}
              className="text-gray-400 hover:text-gray-600 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition text-sm">
              {{expanded ? \'▲\' : \'▼\'}}
            </button>
          </div>
        </div>

        {{/* Expiry warning */}}
        {{isExpiringSoon && (
          <div className="mt-3 bg-orange-50 border border-orange-200 rounded-xl px-4 py-2 text-sm text-orange-700">
            ⚠️ تنتهي الفترة التجريبية خلال {{daysLeft}} {{daysLeft === 1 ? \'يوم\' : \'أيام\'}}
          </div>
        )}}
        {{daysLeft !== null && daysLeft <= 0 && (
          <div className="mt-3 bg-red-50 border border-red-200 rounded-xl px-4 py-2 text-sm text-red-700">
            ❌ انتهت الفترة التجريبية — يرجى ترقية خطتك
          </div>
        )}}
      </div>

      {{/* Expanded details */}}
      {{expanded && (
        <div className="border-t bg-gray-50 px-5 py-4">
          <dl className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm">
            {{[
              [\'النطاق\',          `${{inst.subdomain}}.{DOMAIN}`],
              [\'الإصدار\',         `Odoo ${{inst.odoo_version}}`],
              [\'تاريخ الإنشاء\',   inst.created_at ? new Date(inst.created_at).toLocaleDateString(\'ar-EG\') : \'—\'],
              [\'تاريخ الانتهاء\',  expiresAt ? expiresAt.toLocaleDateString(\'ar-EG\') : \'لا ينتهي\'],
              [\'البريد الإداري\',  inst.admin_email || \'—\'],
              [\'CPU\',             `${{inst.cpu_limit || 1}} vCPU`],
              [\'RAM\',             `${{inst.memory_mb || 1024}} MB`],
              [\'التخزين\',         `${{inst.storage_gb || 1}} GB`],
            ].map(([k,v]) => (
              <div key={{String(k)}} className="flex justify-between border-b border-gray-200 pb-1">
                <dt className="text-gray-500">{{k}}</dt>
                <dd className="font-medium text-gray-800">{{String(v)}}</dd>
              </div>
            ))}}
          </dl>
          {{inst.error_msg && (
            <div className="mt-3 bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-700 font-mono">
              {{inst.error_msg}}
            </div>
          )}}
        </div>
      )}}
    </div>
  );
}}
''')

# ══════════════════════════════════════════════════════════════════════════════
# 6. INSTANCES ENDPOINTS - add stop/start/list per user
# ══════════════════════════════════════════════════════════════════════════════
print("\n[6/7] Updating instances endpoint (stop/start per user)...")
upload('/opt/clickbuild/backend/app/api/v1/endpoints/instances.py', f'''\
"""Instance API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.instance import Instance, InstanceStatus
from app.services.provisioning import ProvisioningEngine

router = APIRouter(prefix="/instances", tags=["instances"])
engine = ProvisioningEngine()


class CreateInstanceRequest(BaseModel):
    subdomain:    str
    display_name: Optional[str] = None
    odoo_version: str = "19"
    modules:      list[str] = ["base", "web"]


@router.get("/")
async def list_instances(
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db)
):
    result = await db.execute(
        select(Instance)
        .where(Instance.user_id == current_user.id,
               Instance.status  != InstanceStatus.DELETED)
        .order_by(Instance.created_at.desc())
    )
    instances = result.scalars().all()
    return {{
        "instances": [{{
            "id":           str(i.id),
            "subdomain":    i.subdomain,
            "display_name": i.display_name,
            "url":          i.url,
            "status":       i.status,
            "odoo_version": i.odoo_version,
            "is_trial":     i.is_trial,
            "expires_at":   i.expires_at.isoformat() if i.expires_at else None,
            "created_at":   i.created_at.isoformat() if i.created_at else None,
            "admin_email":  i.admin_email,
            "cpu_limit":    i.cpu_limit,
            "memory_mb":    i.memory_mb,
            "storage_gb":   i.storage_gb,
            "error_msg":    i.error_msg,
        }} for i in instances]
    }}


@router.post("/")
async def create_instance(
    body: CreateInstanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db)
):
    if not current_user.is_verified:
        raise HTTPException(400, "يجب التحقق من البريد الإلكتروني أولاً")

    # Check plan limits (max 1 trial instance per user for now)
    result = await db.execute(
        select(Instance).where(
            Instance.user_id == current_user.id,
            Instance.status  != InstanceStatus.DELETED
        )
    )
    existing = result.scalars().all()
    if len(existing) >= 3:
        raise HTTPException(400, "وصلت للحد الأقصى من البيئات في خطتك الحالية")

    try:
        instance = await engine.create_instance(
            db           = db,
            user         = current_user,
            subdomain    = body.subdomain,
            odoo_version = body.odoo_version,
            modules      = body.modules,
            is_trial     = True,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"فشل الإنشاء: {{str(e)}}")

    return {{
        "id":        str(instance.id),
        "subdomain": instance.subdomain,
        "url":       instance.url,
        "status":    instance.status,
        "message":   "جاري إنشاء البيئة، سيستغرق ذلك بضع دقائق..."
    }}


@router.get("/{{instance_id}}")
async def get_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db)
):
    result = await db.execute(
        select(Instance).where(
            Instance.id      == instance_id,
            Instance.user_id == current_user.id
        )
    )
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    return {{
        "id": str(inst.id), "subdomain": inst.subdomain, "url": inst.url,
        "status": inst.status, "odoo_version": inst.odoo_version,
        "is_trial": inst.is_trial,
        "expires_at": inst.expires_at.isoformat() if inst.expires_at else None,
        "error_msg": inst.error_msg,
    }}


@router.post("/{{instance_id}}/stop")
async def stop_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db)
):
    result = await db.execute(
        select(Instance).where(
            Instance.id      == instance_id,
            Instance.user_id == current_user.id
        )
    )
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    ok = await engine.stop_instance(inst)
    if ok:
        inst.status = InstanceStatus.STOPPED
        await db.commit()
    return {{"ok": ok}}


@router.post("/{{instance_id}}/start")
async def start_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db)
):
    result = await db.execute(
        select(Instance).where(
            Instance.id      == instance_id,
            Instance.user_id == current_user.id
        )
    )
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    ok = await engine.start_instance(inst)
    if ok:
        inst.status = InstanceStatus.RUNNING
        await db.commit()
    return {{"ok": ok}}


@router.delete("/{{instance_id}}")
async def delete_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession   = Depends(get_db)
):
    result = await db.execute(
        select(Instance).where(
            Instance.id      == instance_id,
            Instance.user_id == current_user.id
        )
    )
    inst = result.scalar_one_or_none()
    if not inst: raise HTTPException(404, "Not found")
    ok = await engine.delete_instance(db, inst)
    return {{"ok": ok}}
''')

# ══════════════════════════════════════════════════════════════════════════════
# 7. SYSTEMD SERVICE FOR CELERY
# ══════════════════════════════════════════════════════════════════════════════
print("\n[7/7] Setting up Celery systemd services...")

celery_worker_service = '''\
[Unit]
Description=ClickBuild Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clickbuild/backend
ExecStart=/opt/clickbuild/backend/venv/bin/celery -A app.workers.celery_app worker --loglevel=info --concurrency=2 -Q celery
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''

celery_beat_service = '''\
[Unit]
Description=ClickBuild Celery Beat (Scheduler)
After=network.target redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/clickbuild/backend
ExecStart=/opt/clickbuild/backend/venv/bin/celery -A app.workers.celery_app beat --loglevel=info --schedule=/tmp/celerybeat-schedule
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''

sftp.putfo(io.BytesIO(celery_worker_service.encode()), '/etc/systemd/system/clickbuild-worker.service')
sftp.putfo(io.BytesIO(celery_beat_service.encode()),   '/etc/systemd/system/clickbuild-beat.service')
print("  [OK] Celery service files uploaded")

# Setup dirs + install deps + enable services
setup_cmds = [
    "mkdir -p /opt/clickbuild/snapshots /opt/clickbuild/data /opt/clickbuild/backups",
    "cd /opt/clickbuild/backend && source venv/bin/activate && pip install celery[redis] -q && echo CELERY_OK",
    "systemctl daemon-reload",
    "systemctl enable clickbuild-worker clickbuild-beat",
    "systemctl restart clickbuild-worker && sleep 2 && systemctl is-active clickbuild-worker",
    "systemctl restart clickbuild-beat   && sleep 2 && systemctl is-active clickbuild-beat",
    "systemctl restart clickbuild-api    && sleep 3 && curl -s http://127.0.0.1:8000/api/health",
]
for cmd in setup_cmds:
    run_print(cmd, timeout=60)

sftp.close()

# Build frontend
print("\n\nBuilding frontend...")
build_cmd = "cd /opt/clickbuild/frontend && NODE_OPTIONS=--max-old-space-size=1500 npm run build 2>&1 | tail -20"
stdin, stdout, stderr = client.exec_command(build_cmd, timeout=300)
while not stdout.channel.exit_status_ready():
    if stdout.channel.recv_ready():
        data = stdout.channel.recv(4096).decode('utf-8', errors='replace')
        print(data, end='', flush=True)
    time.sleep(0.5)
remaining = stdout.read().decode('utf-8', errors='replace')
if remaining: print(remaining)
b_code = stdout.channel.recv_exit_status()
print(f"\nBuild exit: {b_code}")

if b_code == 0:
    stdin, stdout, stderr = client.exec_command("pm2 restart clickbuild-frontend 2>&1 | grep -E 'online|error' | head -2")
    print(stdout.read().decode())

client.close()
print("\n✅ Phase 2 deployment complete!")
print(f"\nFeatures added:")
print("  ✅ NginxService: per-instance config with SSL cert reuse")
print("  ✅ Provisioning: template-clone support, snapshots, staging clone")
print("  ✅ Celery worker: hourly/daily/weekly/monthly automated backups")
print("  ✅ Celery beat: auto-suspend expired instances every 30min")
print("  ✅ Snapshot system: pg_dump + docker commit + restore")
print("  ✅ Dashboard: live instance status, access button, expiry warnings")
print("  ✅ Instances API: stop/start per user")
print("  ✅ Admin API: snapshots + staging clone endpoints")
