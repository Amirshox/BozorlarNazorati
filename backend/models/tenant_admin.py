from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class TenantAdmin(BaseModel):
    __tablename__ = "tenant_admins"

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    password = Column(String, nullable=True)
    photo = Column(String, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=False)

    activation_codes = relationship("TenantAdminActivationCode", back_populates="tenant_admin")

    __table_args__ = (UniqueConstraint("email", "tenant_id", name="unique_email_tenant"),)


class TenantAdminActivationCode(BaseModel):
    __tablename__ = "tenant_admin_activation_codes"

    code = Column(String, nullable=False)
    tenant_admin_id = Column(Integer, ForeignKey("tenant_admins.id"), nullable=False)
    tenant_admin = relationship("TenantAdmin", back_populates="activation_codes")
    __table_args__ = (UniqueConstraint("code", name="unique_code"),)

