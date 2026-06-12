from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Float, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class PlanName(str, enum.Enum):
    TRIAL      = "trial"
    STARTER    = "starter"
    BUSINESS   = "business"
    ENTERPRISE = "enterprise"


class SubStatus(str, enum.Enum):
    TRIAL     = "trial"
    ACTIVE    = "active"
    PAST_DUE  = "past_due"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


class PaymentGateway(str, enum.Enum):
    PAYMOB   = "paymob"    # مصر - بطاقة / فودافون كاش / فوري
    FAWRY    = "fawry"     # مصر - فوري
    PAYTABS  = "paytabs"   # دول الخليج


class Currency(str, enum.Enum):
    EGP = "EGP"
    SAR = "SAR"
    AED = "AED"
    KWD = "KWD"
    USD = "USD"


class Plan(Base):
    __tablename__ = "plans"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name         = Column(Enum(PlanName), unique=True, nullable=False)
    name_ar      = Column(String(50), nullable=False)
    name_en      = Column(String(50), nullable=False)

    # Pricing (per currency)
    price_egp    = Column(Numeric(10, 2), default=0)
    price_sar    = Column(Numeric(10, 2), default=0)
    price_aed    = Column(Numeric(10, 2), default=0)
    price_usd    = Column(Numeric(10, 2), default=0)

    # Limits
    max_users    = Column(Integer, default=3)
    storage_gb   = Column(Float, default=1.0)
    max_instances= Column(Integer, default=1)
    cpu_limit    = Column(Float, default=1.0)
    memory_mb    = Column(Integer, default=1024)

    # Features (JSON)
    features_ar  = Column(JSONB, default=list)
    features_en  = Column(JSONB, default=list)
    is_active    = Column(Boolean, default=True)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id          = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    instance_id      = Column(UUID(as_uuid=True), ForeignKey("instances.id"), nullable=True)

    status           = Column(Enum(SubStatus), default=SubStatus.TRIAL)
    payment_gateway  = Column(Enum(PaymentGateway), nullable=True)
    currency         = Column(Enum(Currency), default=Currency.EGP)
    amount           = Column(Numeric(10, 2), default=0)

    # Payment refs
    gateway_order_id = Column(String(100), nullable=True)
    gateway_sub_id   = Column(String(100), nullable=True)

    started_at       = Column(DateTime(timezone=True), server_default=func.now())
    expires_at       = Column(DateTime(timezone=True), nullable=True)
    cancelled_at     = Column(DateTime(timezone=True), nullable=True)
    next_billing_at  = Column(DateTime(timezone=True), nullable=True)

    # Relations
    user     = relationship("User", back_populates="subscriptions")
    plan     = relationship("Plan", back_populates="subscriptions")
    instance = relationship("Instance", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription")


class Payment(Base):
    __tablename__ = "payments"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=False)

    amount          = Column(Numeric(10, 2), nullable=False)
    currency        = Column(Enum(Currency), nullable=False)
    gateway         = Column(Enum(PaymentGateway), nullable=False)
    gateway_tx_id   = Column(String(100), nullable=True)
    status          = Column(String(20), default="pending")  # pending/success/failed/refunded

    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    paid_at         = Column(DateTime(timezone=True), nullable=True)

    subscription    = relationship("Subscription", back_populates="payments")
