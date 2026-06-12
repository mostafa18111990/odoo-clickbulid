from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import uuid

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, UserCountry
from app.models.subscription import Subscription, Payment, Plan, PlanName, SubStatus, PaymentGateway, Currency
from app.models.instance import Instance
from app.services.payment.paymob import PayMobService
from app.services.payment.paytabs import PayTabsService
from app.core.config import settings

router = APIRouter(prefix="/payments", tags=["payments"])

COUNTRY_GATEWAY = {
    UserCountry.EG: PaymentGateway.PAYMOB,
    # الدول الخليجية → PayTabs
    UserCountry.SA: PaymentGateway.PAYTABS,
    UserCountry.AE: PaymentGateway.PAYTABS,
    UserCountry.KW: PaymentGateway.PAYTABS,
    UserCountry.QA: PaymentGateway.PAYTABS,
    UserCountry.BH: PaymentGateway.PAYTABS,
    UserCountry.OM: PaymentGateway.PAYTABS,
    UserCountry.JO: PaymentGateway.PAYTABS,
}

COUNTRY_CURRENCY = {
    UserCountry.EG:    Currency.EGP,
    UserCountry.SA:    Currency.SAR,
    UserCountry.AE:    Currency.AED,
}


class InitiatePaymentRequest(BaseModel):
    plan_name:      PlanName
    instance_id:    str
    payment_method: str = "card"   # card | wallet | fawry (مصر فقط)


@router.get("/plans")
async def get_plans(db: AsyncSession = Depends(get_db)):
    """جلب الباقات المتاحة"""
    result = await db.execute(select(Plan).where(Plan.is_active == True))
    plans = result.scalars().all()

    return {"plans": [
        {
            "id":          str(p.id),
            "name":        p.name,
            "name_ar":     p.name_ar,
            "name_en":     p.name_en,
            "prices": {
                "EGP": float(p.price_egp),
                "SAR": float(p.price_sar),
                "AED": float(p.price_aed),
                "USD": float(p.price_usd),
            },
            "max_users":   p.max_users,
            "storage_gb":  p.storage_gb,
            "features_ar": p.features_ar,
            "features_en": p.features_en,
        }
        for p in plans
    ]}


@router.post("/initiate")
async def initiate_payment(
    body: InitiatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """بدء عملية الدفع - يعيد رابط الدفع المناسب حسب الدولة"""

    # جلب الباقة
    plan_result = await db.execute(select(Plan).where(Plan.name == body.plan_name))
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(status_code=404, detail="الباقة غير موجودة")

    # تحديد البوابة والعملة حسب دولة العميل
    gateway  = COUNTRY_GATEWAY.get(current_user.country, PaymentGateway.PAYTABS)
    currency = COUNTRY_CURRENCY.get(current_user.country, Currency.USD)

    amount = {
        Currency.EGP: float(plan.price_egp),
        Currency.SAR: float(plan.price_sar),
        Currency.AED: float(plan.price_aed),
        Currency.USD: float(plan.price_usd),
    }[currency]

    order_id = f"CB-{uuid.uuid4().hex[:12].upper()}"

    # إنشاء سجل الاشتراك (pending)
    subscription = Subscription(
        user_id         = current_user.id,
        plan_id         = plan.id,
        instance_id     = body.instance_id,
        status          = SubStatus.TRIAL,
        payment_gateway = gateway,
        currency        = currency,
        amount          = amount,
        gateway_order_id= order_id,
    )
    db.add(subscription)

    payment_record = Payment(
        subscription_id = subscription.id,
        amount          = amount,
        currency        = currency,
        gateway         = gateway,
        status          = "pending",
    )
    db.add(payment_record)
    await db.commit()

    # ─── PayMob (مصر) ───────────────────────────────────────────────────────
    if gateway == PaymentGateway.PAYMOB:
        service = PayMobService()
        result = await service.create_payment_order(
            amount_egp   = amount,
            order_id     = order_id,
            user_email   = current_user.email,
            user_name    = current_user.name,
            user_phone   = current_user.phone or "+201000000000",
            method       = body.payment_method
        )

    # ─── PayTabs (خليج) ──────────────────────────────────────────────────────
    else:
        service = PayTabsService()
        result = await service.create_payment(
            amount       = amount,
            currency     = currency.value,
            order_id     = order_id,
            description  = f"ClickBuild - {plan.name_ar}",
            user_name    = current_user.name,
            user_email   = current_user.email,
            user_phone   = current_user.phone or "+966500000000",
            country_code = current_user.country.value,
        )
        payment_record.gateway_tx_id = result.get("tran_ref")
        await db.commit()

    return {
        "payment_url":     result["payment_url"],
        "order_id":        order_id,
        "amount":          amount,
        "currency":        currency.value,
        "gateway":         gateway.value,
        "subscription_id": str(subscription.id),
    }


@router.post("/paymob/callback")
async def paymob_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """PayMob Webhook"""
    data = await request.json()

    paymob = PayMobService()
    if not paymob.verify_callback(data):
        raise HTTPException(status_code=400, detail="Invalid HMAC")

    order_id  = data.get("order", {}).get("merchant_order_id")
    is_success = data.get("success") == True

    await _process_payment_result(db, order_id, is_success, PaymentGateway.PAYMOB)
    return {"status": "ok"}


@router.post("/paytabs/callback")
async def paytabs_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """PayTabs Webhook"""
    data = await request.json()

    tran_ref   = data.get("tran_ref")
    is_success = data.get("payment_result", {}).get("response_status") == "A"
    order_id   = data.get("cart_id")

    await _process_payment_result(db, order_id, is_success, PaymentGateway.PAYTABS, tran_ref)
    return {"status": "ok"}


@router.get("/success")
async def payment_success():
    return {"message": {"ar": "تمت عملية الدفع بنجاح", "en": "Payment successful"}}


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _process_payment_result(
    db: AsyncSession,
    order_id: str,
    is_success: bool,
    gateway: PaymentGateway,
    tran_ref: str = None
):
    """معالجة نتيجة الدفع وتفعيل الاشتراك"""
    result = await db.execute(
        select(Subscription).where(Subscription.gateway_order_id == order_id)
    )
    subscription = result.scalar_one_or_none()
    if not subscription:
        return

    payment_result = await db.execute(
        select(Payment).where(Payment.subscription_id == subscription.id)
    )
    payment = payment_result.scalar_one_or_none()

    if is_success:
        subscription.status         = SubStatus.ACTIVE
        subscription.started_at     = datetime.now(timezone.utc)
        subscription.expires_at     = datetime.now(timezone.utc) + timedelta(days=30)
        subscription.next_billing_at= datetime.now(timezone.utc) + timedelta(days=30)

        if payment:
            payment.status  = "success"
            payment.paid_at = datetime.now(timezone.utc)
            if tran_ref:
                payment.gateway_tx_id = tran_ref

        # تحويل الـ instance من trial إلى paid
        if subscription.instance_id:
            instance_result = await db.execute(
                select(Instance).where(Instance.id == subscription.instance_id)
            )
            instance = instance_result.scalar_one_or_none()
            if instance:
                instance.is_trial  = False
                instance.expires_at = None
    else:
        if payment:
            payment.status = "failed"

    await db.commit()
