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
    EG = "EG"   # مصر
    SA = "SA"   # السعودية
    AE = "AE"   # الإمارات
    KW = "KW"   # الكويت
    QA = "QA"   # قطر
    BH = "BH"   # البحرين
    OM = "OM"   # عُمان
    JO = "JO"   # الأردن
    OTHER = "OTHER"


class User(Base):
    __tablename__ = "users"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name          = Column(String(100), nullable=False)
    phone         = Column(String(20), nullable=True)
    company_name  = Column(String(100), nullable=True)
    country       = Column(Enum(UserCountry), default=UserCountry.EG)
    language      = Column(Enum(UserLanguage), default=UserLanguage.AR)

    # Auth
    is_verified       = Column(Boolean, default=False)
    is_active         = Column(Boolean, default=True)
    verification_code = Column(String(6), nullable=True)
    reset_token       = Column(String(100), nullable=True)
    reset_token_exp   = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    # Relations
    instances     = relationship("Instance", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user")

    def __repr__(self):
        return f"<User {self.email}>"
