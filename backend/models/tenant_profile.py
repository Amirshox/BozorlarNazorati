from models.base import BaseModel
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy import Column, Integer, String


class TenantProfile(BaseModel):
    __tablename__ = "tenant_profile"

    name = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=True)
    tenants = relationship("Tenant", back_populates="tenant_profile")
    modules = relationship("Module", secondary="tenant_profile_module", back_populates="tenant_profiles")
    roles = relationship("Role", back_populates="tenant_profile")


class TenantProfileModule(BaseModel):
    __tablename__ = "tenant_profile_module"

    tenant_profile_id = Column(Integer, ForeignKey("tenant_profile.id"))
    module_id = Column(Integer, ForeignKey("module.id"))
