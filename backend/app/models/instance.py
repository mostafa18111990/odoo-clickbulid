from sqlalchemy import Column, String, Boolean, DateTime, Enum, Integer, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.core.database import Base


class InstanceStatus(str, enum.Enum):
    PROVISIONING = "provisioning"   # جاري الإنشاء
    RUNNING      = "running"        # يعمل
    STOPPED      = "stopped"        # متوقف
    EXPIRED      = "expired"        # انتهت التجربة
    UPGRADING    = "upgrading"      # جاري الترقية
    ERROR        = "error"          # خطأ
    DELETED      = "deleted"        # محذوف


class Instance(Base):
    __tablename__ = "instances"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id      = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Identity
    subdomain    = Column(String(63), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=True)

    # Odoo
    odoo_version         = Column(String(10), default="19")
    odoo_version_target  = Column(String(10), nullable=True)   # للترقية المستقبلية
    container_id         = Column(String(100), nullable=True)
    container_name       = Column(String(100), nullable=True)
    db_name              = Column(String(100), nullable=True)
    odoo_port            = Column(Integer, nullable=True)
    longpolling_port     = Column(Integer, nullable=True)

    # Auth (مشفرة)
    admin_email  = Column(String(255), nullable=True)
    admin_pass   = Column(String(255), nullable=True)   # encrypted

    # Status
    status       = Column(Enum(InstanceStatus), default=InstanceStatus.PROVISIONING)
    error_msg    = Column(Text, nullable=True)
    is_trial     = Column(Boolean, default=True)

    # Timestamps
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    expires_at   = Column(DateTime(timezone=True), nullable=True)
    deleted_at   = Column(DateTime(timezone=True), nullable=True)

    # Resources
    cpu_limit    = Column(Float, default=1.0)   # vCPU
    memory_mb    = Column(Integer, default=1024)
    storage_gb   = Column(Float, default=1.0)

    # Relations
    user         = relationship("User", back_populates="instances")
    subscription = relationship("Subscription", back_populates="instance", uselist=False)

    @property
    def url(self):
        return f"https://{self.subdomain}.clickbuild.com"

    def __repr__(self):
        return f"<Instance {self.subdomain} odoo{self.odoo_version} {self.status}>"
