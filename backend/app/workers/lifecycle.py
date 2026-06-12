"""
Lifecycle Worker - Celery Tasks
إدارة دورة حياة الـ instances (تذكيرات، إيقاف، حذف)
"""
from celery import Celery
from celery.schedules import crontab
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_

from app.core.config import settings
from app.models.instance import Instance, InstanceStatus

celery_app = Celery(
    "clickbuild",
    broker=f"redis://:{settings.REDIS_PASSWORD}@localhost:6379/0",
    backend=f"redis://:{settings.REDIS_PASSWORD}@localhost:6379/1"
)

celery_app.conf.beat_schedule = {
    # كل ساعة: إيقاف الـ instances المنتهية
    "expire-instances": {
        "task": "app.workers.lifecycle.expire_instances",
        "schedule": crontab(minute=0),
    },
    # كل يوم 9 صباحاً: إرسال تذكيرات
    "send-reminders": {
        "task": "app.workers.lifecycle.send_expiry_reminders",
        "schedule": crontab(hour=9, minute=0),
    },
    # كل أسبوع: حذف الـ instances القديمة نهائياً
    "cleanup-deleted": {
        "task": "app.workers.lifecycle.cleanup_deleted_instances",
        "schedule": crontab(day_of_week=0, hour=2, minute=0),
    },
    # كل 5 دقائق: مراقبة صحة الـ instances
    "health-check": {
        "task": "app.workers.lifecycle.health_check_instances",
        "schedule": crontab(minute="*/5"),
    },
}


@celery_app.task
def expire_instances():
    """إيقاف الـ instances التي انتهت تجربتها"""
    from app.core.database import SyncSession
    from app.services.provisioning import ProvisioningEngine

    engine = ProvisioningEngine()
    now = datetime.now(timezone.utc)

    with SyncSession() as db:
        instances = db.execute(
            select(Instance).where(
                and_(
                    Instance.status == InstanceStatus.RUNNING,
                    Instance.is_trial == True,
                    Instance.expires_at <= now
                )
            )
        ).scalars().all()

        for instance in instances:
            try:
                engine.stop_instance_sync(instance)
                instance.status = InstanceStatus.EXPIRED
                db.commit()
                # إرسال إيميل انتهاء التجربة
                send_expiry_email.delay(str(instance.id))
            except Exception as e:
                instance.error_msg = str(e)
                db.commit()


@celery_app.task
def send_expiry_reminders():
    """إرسال تذكيرات للعملاء قبل انتهاء التجربة"""
    from app.core.database import SyncSession
    from app.services.email_service import EmailService

    now = datetime.now(timezone.utc)
    reminder_days = [7, 3, 1]   # التذكير قبل 7 أيام، 3 أيام، يوم واحد

    with SyncSession() as db:
        for days in reminder_days:
            target_date = now + timedelta(days=days)
            instances = db.execute(
                select(Instance).where(
                    and_(
                        Instance.status == InstanceStatus.RUNNING,
                        Instance.is_trial == True,
                        Instance.expires_at >= target_date,
                        Instance.expires_at < target_date + timedelta(hours=24)
                    )
                )
            ).scalars().all()

            for instance in instances:
                EmailService.send_trial_reminder_sync(
                    instance_id=str(instance.id),
                    days_left=days
                )


@celery_app.task
def cleanup_deleted_instances():
    """حذف البيانات القديمة نهائياً بعد 7 أيام من الانتهاء"""
    from app.core.database import SyncSession
    from app.services.provisioning import ProvisioningEngine

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    engine = ProvisioningEngine()

    with SyncSession() as db:
        instances = db.execute(
            select(Instance).where(
                and_(
                    Instance.status.in_([InstanceStatus.EXPIRED, InstanceStatus.DELETED]),
                    Instance.deleted_at == None,
                    Instance.expires_at <= cutoff
                )
            )
        ).scalars().all()

        for instance in instances:
            try:
                engine.delete_instance_sync(instance, db)
            except Exception:
                pass


@celery_app.task
def health_check_instances():
    """مراقبة صحة الـ instances الشغالة"""
    import docker
    from app.core.database import SyncSession

    client = docker.from_env()

    with SyncSession() as db:
        instances = db.execute(
            select(Instance).where(Instance.status == InstanceStatus.RUNNING)
        ).scalars().all()

        for instance in instances:
            try:
                container = client.containers.get(instance.container_name)
                if container.status != "running":
                    instance.status = InstanceStatus.STOPPED
                    db.commit()
            except docker.errors.NotFound:
                instance.status = InstanceStatus.ERROR
                instance.error_msg = "Container not found"
                db.commit()


@celery_app.task
def send_expiry_email(instance_id: str):
    from app.core.database import SyncSession
    from app.services.email_service import EmailService
    from app.models.user import User

    with SyncSession() as db:
        instance = db.get(Instance, instance_id)
        if instance:
            user = db.get(User, instance.user_id)
            if user:
                EmailService.send_trial_expired_sync(user, instance)
