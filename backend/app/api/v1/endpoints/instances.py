from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
from typing import Optional
import re

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.instance import Instance, InstanceStatus
from app.services.provisioning import ProvisioningEngine
from app.core.security import decrypt_secret

router = APIRouter(prefix="/instances", tags=["instances"])
engine = ProvisioningEngine()

RESERVED_SUBDOMAINS = {
    "www", "api", "admin", "mail", "ftp", "ssh", "ns1", "ns2",
    "app", "dashboard", "portal", "support", "help", "blog",
    "clickbuild", "static", "cdn", "assets"
}

AVAILABLE_MODULES = {
    "accounting":   {"ar": "المحاسبة",       "en": "Accounting"},
    "sales":        {"ar": "المبيعات",        "en": "Sales"},
    "purchase":     {"ar": "المشتريات",       "en": "Purchase"},
    "inventory":    {"ar": "المخزون",         "en": "Inventory"},
    "hr":           {"ar": "الموارد البشرية", "en": "HR"},
    "crm":          {"ar": "إدارة العملاء",   "en": "CRM"},
    "project":      {"ar": "إدارة المشاريع",  "en": "Project"},
    "website":      {"ar": "الموقع الإلكتروني","en": "Website"},
    "ecommerce":    {"ar": "التجارة الإلكترونية","en": "eCommerce"},
    "manufacturing":{"ar": "التصنيع",         "en": "Manufacturing"},
    "pos":          {"ar": "نقاط البيع",      "en": "Point of Sale"},
}


class CreateInstanceRequest(BaseModel):
    subdomain: str
    modules:   list[str] = ["accounting", "sales"]
    language:  str = "ar"

    @field_validator("subdomain")
    @classmethod
    def validate_subdomain(cls, v):
        v = v.lower().strip()
        if not re.match(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$', v):
            raise ValueError("اسم الشركة يحتوي على أحرف غير مسموح بها")
        if v in RESERVED_SUBDOMAINS:
            raise ValueError("هذا الاسم محجوز")
        return v

    @field_validator("modules")
    @classmethod
    def validate_modules(cls, v):
        invalid = [m for m in v if m not in AVAILABLE_MODULES]
        if invalid:
            raise ValueError(f"وحدات غير معروفة: {invalid}")
        return v


class UpgradeRequest(BaseModel):
    target_version: str

    @field_validator("target_version")
    @classmethod
    def validate_version(cls, v):
        if not re.match(r'^\d+$', v):
            raise ValueError("إصدار غير صالح")
        return v


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/modules")
async def list_modules():
    """قائمة الوحدات المتاحة"""
    return {"modules": AVAILABLE_MODULES}


@router.post("/check-subdomain")
async def check_subdomain(subdomain: str, db: AsyncSession = Depends(get_db)):
    """التحقق من توفر اسم الشركة"""
    subdomain = subdomain.lower().strip()

    if subdomain in RESERVED_SUBDOMAINS:
        return {"available": False, "reason": {"ar": "هذا الاسم محجوز", "en": "This name is reserved"}}

    if not re.match(r'^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$', subdomain):
        return {"available": False, "reason": {"ar": "الاسم يحتوي على رموز غير مسموحة", "en": "Invalid characters"}}

    result = await db.execute(
        select(Instance).where(
            Instance.subdomain == subdomain,
            Instance.status != InstanceStatus.DELETED
        )
    )
    if result.scalar_one_or_none():
        return {"available": False, "reason": {"ar": "الاسم محجوز مسبقاً", "en": "Already taken"}}

    return {"available": True, "url": f"https://{subdomain}.clickbuild.com"}


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def create_instance(
    body: CreateInstanceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """إنشاء Odoo instance جديدة"""

    # تحقق من الحد المسموح (عميل مجاني: instance واحدة فقط)
    existing = await db.execute(
        select(Instance).where(
            Instance.user_id == current_user.id,
            Instance.status.not_in([InstanceStatus.DELETED, InstanceStatus.EXPIRED])
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ar": "لديك instance نشطة مسبقاً", "en": "You already have an active instance"}
        )

    try:
        instance = await engine.create_instance(
            db          = db,
            user        = current_user,
            subdomain   = body.subdomain,
            modules     = body.modules,
            is_trial    = True
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "message":    {"ar": "جاري إنشاء بيئتك، ستصلك رسالة عند الجاهزية", "en": "Creating your environment, you'll be notified when ready"},
        "instance_id": str(instance.id),
        "subdomain":   instance.subdomain,
        "url":         instance.url,
        "status":      instance.status,
        "expires_at":  instance.expires_at,
    }


@router.get("/")
async def list_instances(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """قائمة instances العميل"""
    result = await db.execute(
        select(Instance).where(
            Instance.user_id == current_user.id,
            Instance.status != InstanceStatus.DELETED
        )
    )
    instances = result.scalars().all()

    return {"instances": [
        {
            "id":            str(i.id),
            "subdomain":     i.subdomain,
            "url":           i.url,
            "status":        i.status,
            "odoo_version":  i.odoo_version,
            "is_trial":      i.is_trial,
            "expires_at":    i.expires_at,
            "upgrade_available": _check_upgrade_available(i.odoo_version),
        }
        for i in instances
    ]}


@router.get("/{instance_id}")
async def get_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    instance = await _get_user_instance(instance_id, current_user, db)
    return {
        "id":            str(instance.id),
        "subdomain":     instance.subdomain,
        "url":           instance.url,
        "status":        instance.status,
        "odoo_version":  instance.odoo_version,
        "admin_email":   instance.admin_email,
        "is_trial":      instance.is_trial,
        "expires_at":    instance.expires_at,
        "created_at":    instance.created_at,
        "upgrade_available": _check_upgrade_available(instance.odoo_version),
    }


@router.post("/{instance_id}/start")
async def start_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    instance = await _get_user_instance(instance_id, current_user, db)
    if instance.status not in [InstanceStatus.STOPPED, InstanceStatus.EXPIRED]:
        raise HTTPException(status_code=400, detail="الـ instance ليست متوقفة")
    await engine.start_instance(instance)
    return {"message": {"ar": "تم تشغيل البيئة", "en": "Instance started"}}


@router.post("/{instance_id}/stop")
async def stop_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    instance = await _get_user_instance(instance_id, current_user, db)
    await engine.stop_instance(instance)
    return {"message": {"ar": "تم إيقاف البيئة", "en": "Instance stopped"}}


@router.post("/{instance_id}/upgrade")
async def upgrade_instance(
    instance_id: str,
    body: UpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    instance = await _get_user_instance(instance_id, current_user, db)

    if int(body.target_version) <= int(instance.odoo_version):
        raise HTTPException(status_code=400, detail={"ar": "يجب أن يكون الإصدار الجديد أحدث", "en": "Target version must be newer"})

    await engine.upgrade_instance(db, instance, body.target_version)
    return {
        "message": {"ar": f"جاري الترقية إلى Odoo {body.target_version}", "en": f"Upgrading to Odoo {body.target_version}"},
        "target_version": body.target_version
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_user_instance(instance_id: str, user: User, db: AsyncSession) -> Instance:
    result = await db.execute(
        select(Instance).where(
            Instance.id == instance_id,
            Instance.user_id == user.id
        )
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance غير موجودة")
    return instance


def _check_upgrade_available(current_version: str) -> dict:
    """التحقق من توفر إصدار أحدث"""
    from app.core.config import settings
    available = [v for v in settings.ODOO_VERSIONS if int(v) > int(current_version)]
    return {
        "available": len(available) > 0,
        "versions": available
    }
