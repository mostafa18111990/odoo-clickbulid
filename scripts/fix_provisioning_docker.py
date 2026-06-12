#!/usr/bin/env python
"""Fix Docker provisioning: correct entrypoint + gateway IP for DB"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
HOST = "129.121.98.243"; USER = "root"; PASS = "Mh@01007121878"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=30)
sftp = client.open_sftp()

DOMAIN      = "odoo.clickbulid.com"
DOCKER_GW   = "172.18.0.1"   # docker clickbuild-net gateway → host PostgreSQL

def upload(path, content):
    sftp.putfo(io.BytesIO(content.encode('utf-8')), path)
    print(f"  [OK] {path}")

def run(cmd, timeout=20):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Add DOCKER_POSTGRES_HOST to .env
print("[1/3] Updating .env...")
env_content = run("cat /opt/clickbuild/backend/.env")
if "DOCKER_POSTGRES_HOST" not in env_content:
    env_content += f"\n# Docker containers use gateway to reach host PostgreSQL\nDOCKER_POSTGRES_HOST={DOCKER_GW}\n"
    sftp.putfo(io.BytesIO(env_content.encode()), '/opt/clickbuild/backend/.env')
    print(f"  Added DOCKER_POSTGRES_HOST={DOCKER_GW}")
else:
    print("  Already set")

# 2. Update config.py to add DOCKER_POSTGRES_HOST
print("[2/3] Checking config.py for DOCKER_POSTGRES_HOST...")
cfg = run("cat /opt/clickbuild/backend/app/core/config.py")
if "DOCKER_POSTGRES_HOST" not in cfg:
    # Add after POSTGRES_HOST line
    cfg = cfg.replace(
        "POSTGRES_HOST: str = \"localhost\"",
        "POSTGRES_HOST: str = \"localhost\"\n    DOCKER_POSTGRES_HOST: str = \"172.18.0.1\"  # Host IP from inside Docker containers"
    )
    sftp.putfo(io.BytesIO(cfg.encode()), '/opt/clickbuild/backend/app/core/config.py')
    print("  Updated config.py")
else:
    print("  Already configured")

# 3. Fix provisioning.py - correct entrypoint + docker gateway
print("[3/3] Fixing provisioning.py (entrypoint + gateway)...")
upload('/opt/clickbuild/backend/app/services/provisioning.py', f'''\
"""Provisioning Engine - Core of the platform"""
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

TEMPLATE_DB  = "clickbuild_template"
BACKUP_DIR   = Path("/opt/clickbuild/backups")
SNAPSHOT_DIR = Path("/opt/clickbuild/snapshots")
DATA_DIR     = Path("/opt/clickbuild/data")
DOCKER_GW    = "{DOCKER_GW}"   # host PostgreSQL IP from inside containers


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

    async def clone_instance(self, db: AsyncSession, source: Instance,
                             new_subdomain: str, is_staging: bool = True) -> Instance:
        user_res = await db.execute(select(User).where(User.id == source.user_id))
        user = user_res.scalar_one()
        clone = await self.create_instance(
            db, user, new_subdomain,
            odoo_version=source.odoo_version,
            is_trial=False, from_template=False
        )
        asyncio.create_task(
            self._clone_db_when_ready(source.db_name, clone.db_name, clone.id, db)
        )
        return clone

    async def take_snapshot(self, instance: Instance) -> dict:
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        name     = f"{{instance.subdomain}}_{{ts}}"
        snap_dir = SNAPSHOT_DIR / instance.subdomain
        snap_dir.mkdir(parents=True, exist_ok=True)
        db_file  = snap_dir / f"{{name}}.sql.gz"
        env = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
        subprocess.run([
            "pg_dump", "-h", settings.POSTGRES_HOST,
            "-U", settings.POSTGRES_USER, "-d", instance.db_name,
            "--compress=9", "-f", str(db_file)
        ], env=env, check=True)
        try:
            c   = self.docker_client.containers.get(instance.container_name)
            img = c.commit(repository=f"clickbuild/snap_{{instance.subdomain}}", tag=ts)
            docker_image = img.id
        except Exception:
            docker_image = None
        size = db_file.stat().st_size if db_file.exists() else 0
        return {{"name": name, "timestamp": ts, "size_mb": round(size/1e6,2), "docker_image": docker_image}}

    def list_snapshots(self, subdomain: str) -> list:
        snap_dir = SNAPSHOT_DIR / subdomain
        if not snap_dir.exists():
            return []
        snaps = []
        for f in sorted(snap_dir.glob("*.sql.gz"), reverse=True)[:20]:
            stat = f.stat()
            snaps.append({{
                "name": f.stem.replace(".sql", ""),
                "size_mb": round(stat.st_size/1e6, 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }})
        return snaps

    async def restore_snapshot(self, instance: Instance, snapshot_name: str) -> bool:
        snap_dir = SNAPSHOT_DIR / instance.subdomain
        db_file  = snap_dir / f"{{snapshot_name}}.sql.gz"
        if not db_file.exists():
            raise FileNotFoundError(f"Snapshot not found: {{snapshot_name}}")
        await self.stop_instance(instance)
        await asyncio.sleep(2)
        self._drop_database(instance.db_name)
        self._create_database(instance.db_name, from_template=False)
        env = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
        proc = subprocess.run(
            f"gunzip -c {{db_file}} | psql -h {{settings.POSTGRES_HOST}} -U {{settings.POSTGRES_USER}} {{instance.db_name}}",
            shell=True, env=env
        )
        if proc.returncode != 0:
            raise Exception("DB restore failed")
        await self.start_instance(instance)
        return True

    async def upgrade_instance(self, db: AsyncSession, instance: Instance, target_version: str) -> bool:
        instance.status = InstanceStatus.UPGRADING
        instance.odoo_version_target = target_version
        await db.commit()
        asyncio.create_task(self._upgrade_async(instance, target_version, db))
        return True

    # ─── Private: Provisioning ────────────────────────────────────────────────

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
            await asyncio.get_event_loop().run_in_executor(
                None, self._create_database, db_name, from_template
            )
            container = await asyncio.get_event_loop().run_in_executor(
                None, self._start_container,
                container_name, db_name, port, longpolling_port,
                odoo_version, modules, user, admin_pass,
                not from_template
            )
            instance.container_id = container.id
            await self._wait_for_odoo(port)
            self.nginx.add_instance_config(
                subdomain=instance.subdomain,
                port=port,
                longpolling_port=longpolling_port,
                odoo_version=odoo_version
            )
            instance.status = InstanceStatus.RUNNING
            await db.commit()
            await EmailService.send_instance_ready(
                email=user.email, name=user.name,
                subdomain=instance.subdomain, admin_pass=admin_pass,
                expires_at=instance.expires_at, language=user.language
            )
        except Exception as e:
            instance.status    = InstanceStatus.ERROR
            instance.error_msg = str(e)[:500]
            await db.commit()

    def _start_container(
        self, name, db_name, port, lp_port,
        version, modules, user, admin_pass, init_db=True
    ):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data_vol = DATA_DIR / db_name
        data_vol.mkdir(parents=True, exist_ok=True)

        return self.docker_client.containers.run(
            image      = f"clickbuild/odoo:{{version}}",
            name       = name,
            entrypoint = "/entrypoint.sh",   # fix broken image metadata
            detach     = True,
            restart_policy = {{"Name": "unless-stopped"}},
            network    = "clickbuild-net",
            extra_hosts = {{"dockerhost": DOCKER_GW}},
            ports      = {{
                "8069/tcp": ("127.0.0.1", port),
                "8072/tcp": ("127.0.0.1", lp_port),
            }},
            environment = {{
                "DB_HOST"        : DOCKER_GW,   # gateway IP, not localhost
                "DB_PORT"        : "5432",
                "DB_USER"        : settings.POSTGRES_USER,
                "DB_PASSWORD"    : settings.POSTGRES_PASSWORD,
                "DB_NAME"        : db_name,
                "MASTER_PASSWORD": settings.ODOO_MASTER_PASSWORD,
                "ADMIN_EMAIL"    : user.email,
                "ADMIN_PASSWORD" : admin_pass,
                "COMPANY_NAME"   : user.company_name or user.name,
                "ODOO_MODULES"   : ",".join(modules),
                "ODOO_LANG"      : "ar_001,en_US",
                "WITHOUT_DEMO"   : "all",
                "INIT_DB"        : "true" if init_db else "false",
                "ODOO_VERSION"   : version,
                "SMTP_HOST"      : settings.SMTP_HOST,
                "SMTP_PORT"      : str(settings.SMTP_PORT),
                "SMTP_SSL"       : "true",
                "SMTP_USER"      : settings.SMTP_USER,
                "SMTP_PASSWORD"  : settings.SMTP_PASSWORD,
                "EMAIL_FROM"     : settings.EMAIL_FROM,
            }},
            mem_limit  = "1g",
            cpu_period = 100000,
            cpu_quota  = 100000,
            volumes    = {{str(data_vol): {{"bind": "/var/lib/odoo", "mode": "rw"}}}}
        )

    async def _clone_db_when_ready(self, src_db, dest_db, instance_id, db):
        await asyncio.sleep(5)
        result = await db.execute(select(Instance).where(Instance.id == instance_id))
        instance = result.scalar_one_or_none()
        if not instance: return
        try:
            self._drop_database(dest_db)
            env = {{**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD}}
            dump = subprocess.run([
                "pg_dump", "-h", settings.POSTGRES_HOST,
                "-U", settings.POSTGRES_USER, "-d", src_db,
                "--no-owner", "--no-acl", "--format=custom"
            ], env=env, capture_output=True, check=True)
            self._create_database(dest_db, from_template=False)
            subprocess.run([
                "pg_restore", "-h", settings.POSTGRES_HOST,
                "-U", settings.POSTGRES_USER, "-d", dest_db,
                "--no-owner", "--no-acl"
            ], env=env, input=dump.stdout, check=True)
        except Exception as e:
            pass

    async def _upgrade_async(self, instance: Instance, target_version: str, db: AsyncSession):
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._backup_database, instance.db_name
            )
            try:
                old = self.docker_client.containers.get(instance.container_name)
                old.stop(timeout=30); old.remove()
            except Exception: pass

            data_vol = DATA_DIR / instance.db_name
            container = self.docker_client.containers.run(
                image=f"clickbuild/odoo:{{target_version}}",
                name=instance.container_name,
                entrypoint="/entrypoint.sh",
                detach=True,
                restart_policy={{"Name": "unless-stopped"}},
                network="clickbuild-net",
                extra_hosts={{"dockerhost": DOCKER_GW}},
                ports={{
                    "8069/tcp": ("127.0.0.1", instance.odoo_port),
                    "8072/tcp": ("127.0.0.1", instance.longpolling_port),
                }},
                environment={{
                    "DB_HOST": DOCKER_GW, "DB_PORT": "5432",
                    "DB_USER": settings.POSTGRES_USER,
                    "DB_PASSWORD": settings.POSTGRES_PASSWORD,
                    "DB_NAME": instance.db_name,
                    "MASTER_PASSWORD": settings.ODOO_MASTER_PASSWORD,
                    "INIT_DB": "false", "ODOO_VERSION": target_version,
                }},
                volumes={{str(data_vol): {{"bind": "/var/lib/odoo", "mode": "rw"}}}},
                mem_limit="1g", cpu_period=100000, cpu_quota=100000
            )
            instance.odoo_version=target_version; instance.odoo_version_target=None
            instance.status=InstanceStatus.RUNNING; instance.container_id=container.id
            await db.commit()
        except Exception as e:
            instance.status=InstanceStatus.ERROR
            instance.error_msg=f"Upgrade failed: {{e}}"
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
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (TEMPLATE_DB,))
        template_exists = cur.fetchone() is not None

        if from_template and template_exists:
            # Fast clone from template
            cur.execute(f"""
                SELECT pg_terminate_backend(pid) FROM pg_stat_activity
                WHERE datname=%s AND pid<>pg_backend_pid()
            """, (TEMPLATE_DB,))
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
                    if r.status == 200: return
            except Exception:
                pass
            await asyncio.sleep(5)
        raise TimeoutError(f"Odoo on port {{port}} did not respond in {{timeout}}s")

    async def _allocate_port(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(func.max(Instance.odoo_port)).where(Instance.status != InstanceStatus.DELETED)
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
                Instance.status    != InstanceStatus.DELETED
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

# Restart API to pick up changes
print("\nRestarting API...")
out = run("systemctl restart clickbuild-api && sleep 4 && curl -s http://127.0.0.1:8000/api/health")
print(f"  API: {out.strip()}")

sftp.close()
client.close()
print("\nDone! Provisioning fixed:")
print(f"  - entrypoint: /entrypoint.sh")
print(f"  - DB_HOST for containers: {DOCKER_GW}")
