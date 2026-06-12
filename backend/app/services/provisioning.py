"""
Provisioning Engine - قلب المنصة
مسؤول عن إنشاء/إيقاف/حذف/ترقية Odoo instances
"""
import asyncio
import docker
import psycopg2
import secrets
import string
import re
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.security import encrypt_secret
from app.models.instance import Instance, InstanceStatus
from app.models.user import User
from app.services.nginx_service import NginxService
from app.services.email_service import EmailService

NGINX_SITES_DIR = "/etc/nginx/sites-available/instances"
NGINX_ENABLED_DIR = "/etc/nginx/sites-enabled"
ODOO_TEMPLATE = "/opt/clickbuild/nginx/instance.template"


class ProvisioningEngine:

    def __init__(self):
        self.docker_client = docker.from_env()
        self.nginx = NginxService()

    # ─── Public API ───────────────────────────────────────────────────────────

    async def create_instance(
        self,
        db: AsyncSession,
        user: User,
        subdomain: str,
        odoo_version: str = "19",
        modules: list[str] = None,
        is_trial: bool = True
    ) -> Instance:
        """إنشاء Odoo instance جديدة كاملة"""

        subdomain = self._sanitize_subdomain(subdomain)
        await self._assert_subdomain_available(db, subdomain)

        port = await self._allocate_port(db)
        longpolling_port = port + 1000
        db_name = f"odoo_{subdomain}"
        container_name = f"odoo_{subdomain}"
        admin_pass = self._generate_password()

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

        # الإنشاء الفعلي في background
        asyncio.create_task(
            self._provision_async(instance.id, db_name, container_name,
                                  port, longpolling_port, odoo_version,
                                  modules or ["base", "web"],
                                  user, admin_pass, db)
        )

        return instance

    async def stop_instance(self, instance: Instance) -> bool:
        try:
            container = self.docker_client.containers.get(instance.container_name)
            container.stop(timeout=10)
            return True
        except docker.errors.NotFound:
            return False

    async def start_instance(self, instance: Instance) -> bool:
        try:
            container = self.docker_client.containers.get(instance.container_name)
            container.start()
            return True
        except docker.errors.NotFound:
            return False

    async def delete_instance(self, db: AsyncSession, instance: Instance) -> bool:
        """حذف كامل للـ instance"""
        try:
            # إيقاف وحذف Container
            try:
                container = self.docker_client.containers.get(instance.container_name)
                container.stop(timeout=5)
                container.remove(force=True)
            except docker.errors.NotFound:
                pass

            # حذف قاعدة البيانات
            self._drop_database(instance.db_name)

            # حذف Nginx config
            self.nginx.remove_instance_config(instance.subdomain)

            # تحديث السجل
            instance.status = InstanceStatus.DELETED
            instance.deleted_at = datetime.now(timezone.utc)
            await db.commit()
            return True

        except Exception as e:
            instance.error_msg = str(e)
            await db.commit()
            return False

    async def upgrade_instance(
        self,
        db: AsyncSession,
        instance: Instance,
        target_version: str
    ) -> bool:
        """ترقية Odoo instance لإصدار أحدث"""
        instance.status = InstanceStatus.UPGRADING
        instance.odoo_version_target = target_version
        await db.commit()

        asyncio.create_task(
            self._upgrade_async(instance, target_version, db)
        )
        return True

    # ─── Private: Core Provisioning ───────────────────────────────────────────

    async def _provision_async(
        self, instance_id, db_name, container_name,
        port, longpolling_port, odoo_version,
        modules, user, admin_pass, db
    ):
        result = await db.execute(
            select(Instance).where(Instance.id == instance_id)
        )
        instance = result.scalar_one_or_none()
        if not instance:
            return

        try:
            # 1. إنشاء قاعدة البيانات
            await asyncio.get_event_loop().run_in_executor(
                None, self._create_database, db_name
            )

            # 2. رفع Docker Container
            container = await asyncio.get_event_loop().run_in_executor(
                None,
                self._start_container,
                container_name, db_name, port, longpolling_port,
                odoo_version, modules, user, admin_pass
            )
            instance.container_id = container.id

            # 3. انتظار حتى يكون جاهزاً
            await self._wait_for_odoo(port)

            # 4. إضافة Nginx config
            self.nginx.add_instance_config(
                subdomain        = instance.subdomain,
                port             = port,
                longpolling_port = longpolling_port,
                odoo_version     = odoo_version
            )

            # 5. تحديث الحالة
            instance.status = InstanceStatus.RUNNING
            await db.commit()

            # 6. إرسال إيميل للعميل
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
            instance.error_msg = str(e)
            await db.commit()
            raise

    def _start_container(
        self, name, db_name, port, lp_port,
        version, modules, user, admin_pass
    ):
        return self.docker_client.containers.run(
            image   = f"clickbuild/odoo:{version}",
            name    = name,
            detach  = True,
            restart_policy = {"Name": "unless-stopped"},
            network = "clickbuild-net",
            ports   = {
                "8069/tcp": ("127.0.0.1", port),
                "8072/tcp": ("127.0.0.1", lp_port),
            },
            environment = {
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
                "INIT_DB"         : "true",
                "ODOO_VERSION"    : version,
                "SMTP_HOST"       : settings.SMTP_HOST,
                "SMTP_PORT"       : str(settings.SMTP_PORT),
                "SMTP_SSL"        : "true",
                "SMTP_USER"       : settings.SMTP_USER,
                "SMTP_PASSWORD"   : settings.SMTP_PASSWORD,
                "EMAIL_FROM"      : settings.EMAIL_FROM,
            },
            mem_limit   = "1g",
            cpu_period  = 100000,
            cpu_quota   = 100000,
            volumes     = {
                f"/opt/clickbuild/data/{db_name}": {"bind": "/var/lib/odoo", "mode": "rw"}
            }
        )

    # ─── Private: Upgrade ─────────────────────────────────────────────────────

    async def _upgrade_async(self, instance: Instance, target_version: str, db: AsyncSession):
        try:
            # 1. أخذ backup
            await asyncio.get_event_loop().run_in_executor(
                None, self._backup_database, instance.db_name
            )

            # 2. إيقاف الـ container القديم
            old_container = self.docker_client.containers.get(instance.container_name)
            old_container.stop(timeout=30)

            # 3. رفع container جديد بالإصدار الجديد
            new_name = f"{instance.container_name}_v{target_version}"
            container = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.docker_client.containers.run(
                    image   = f"clickbuild/odoo:{target_version}",
                    name    = new_name,
                    detach  = True,
                    network = "clickbuild-net",
                    ports   = {
                        "8069/tcp": ("127.0.0.1", instance.odoo_port),
                        "8072/tcp": ("127.0.0.1", instance.longpolling_port),
                    },
                    environment = {
                        "DB_HOST"         : settings.POSTGRES_HOST,
                        "DB_PORT"         : str(settings.POSTGRES_PORT),
                        "DB_USER"         : settings.POSTGRES_USER,
                        "DB_PASSWORD"     : settings.POSTGRES_PASSWORD,
                        "DB_NAME"         : instance.db_name,
                        "MASTER_PASSWORD" : settings.ODOO_MASTER_PASSWORD,
                        "INIT_DB"         : "false",
                        "ODOO_VERSION"    : target_version,
                    },
                    command = ["odoo", "--update=all", "--stop-after-init"]
                )
            )

            # 4. انتظار انتهاء الـ migration
            exit_code = container.wait()["StatusCode"]
            if exit_code != 0:
                raise Exception(f"Upgrade migration failed with code {exit_code}")

            # 5. إعادة تشغيل بالـ image الجديد
            container.remove()
            old_container.remove()

            # ... (إعادة رفع بالإصدار الجديد كـ production)

            instance.odoo_version        = target_version
            instance.odoo_version_target = None
            instance.status              = InstanceStatus.RUNNING
            instance.container_name      = new_name
            await db.commit()

        except Exception as e:
            instance.status    = InstanceStatus.ERROR
            instance.error_msg = f"Upgrade failed: {e}"
            await db.commit()
            raise

    # ─── Private: Helpers ─────────────────────────────────────────────────────

    def _create_database(self, db_name: str):
        conn = psycopg2.connect(
            host     = settings.POSTGRES_HOST,
            port     = settings.POSTGRES_PORT,
            user     = settings.POSTGRES_USER,
            password = settings.POSTGRES_PASSWORD,
            dbname   = "postgres"
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f'CREATE DATABASE "{db_name}" OWNER "{settings.POSTGRES_USER}"')
        cur.close()
        conn.close()

    def _drop_database(self, db_name: str):
        conn = psycopg2.connect(
            host     = settings.POSTGRES_HOST,
            port     = settings.POSTGRES_PORT,
            user     = settings.POSTGRES_USER,
            password = settings.POSTGRES_PASSWORD,
            dbname   = "postgres"
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f"""
            SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
        """, (db_name,))
        cur.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        cur.close()
        conn.close()

    def _backup_database(self, db_name: str):
        import subprocess
        backup_dir = f"/opt/clickbuild/backups"
        Path(backup_dir).mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/{db_name}_{timestamp}.sql.gz"
        subprocess.run([
            "pg_dump",
            "-h", settings.POSTGRES_HOST,
            "-U", settings.POSTGRES_USER,
            "-d", db_name,
            "--compress=9",
            "-f", backup_file
        ], check=True, env={**os.environ, "PGPASSWORD": settings.POSTGRES_PASSWORD})
        return backup_file

    async def _wait_for_odoo(self, port: int, timeout: int = 120):
        import aiohttp
        url = f"http://127.0.0.1:{port}/web/health"
        deadline = asyncio.get_event_loop().time() + timeout
        async with aiohttp.ClientSession() as session:
            while asyncio.get_event_loop().time() < deadline:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as r:
                        if r.status == 200:
                            return
                except Exception:
                    pass
                await asyncio.sleep(3)
        raise TimeoutError(f"Odoo على port {port} لم يستجب في {timeout} ثانية")

    async def _allocate_port(self, db: AsyncSession) -> int:
        """
        Allocate the next free Odoo port.

        RACE-CONDITION FIX (Phase 0 §3.3): take a transaction-level advisory
        lock so two concurrent provisioning requests cannot read the same
        max_port and collide. The lock auto-releases at transaction end.
        """
        from sqlalchemy import func, text
        from app.models.instance import Instance

        # PostgreSQL transaction-scoped advisory lock (arbitrary key 728144).
        # Serializes port allocation across concurrent provisioning calls.
        await db.execute(text("SELECT pg_advisory_xact_lock(728144)"))

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
            raise Exception("نفدت المنافذ المتاحة")
        return next_port

    async def _assert_subdomain_available(self, db: AsyncSession, subdomain: str):
        result = await db.execute(
            select(Instance).where(
                Instance.subdomain == subdomain,
                Instance.status != InstanceStatus.DELETED
            )
        )
        if result.scalar_one_or_none():
            raise ValueError(f"الـ subdomain '{subdomain}' محجوز مسبقاً")

    @staticmethod
    def _sanitize_subdomain(raw: str) -> str:
        s = raw.lower().strip()
        s = re.sub(r"[^a-z0-9-]", "-", s)
        s = re.sub(r"-+", "-", s).strip("-")
        if len(s) < 3:
            raise ValueError("اسم الشركة يجب أن يكون 3 أحرف على الأقل")
        if len(s) > 63:
            raise ValueError("اسم الشركة طويل جداً (أكثر من 63 حرف)")
        return s

    @staticmethod
    def _generate_password(length: int = 16) -> str:
        chars = string.ascii_letters + string.digits + "!@#$"
        return "".join(secrets.choice(chars) for _ in range(length))
