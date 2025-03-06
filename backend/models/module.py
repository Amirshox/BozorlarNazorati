from models.base import BaseModel
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship


class Module(BaseModel):
    __tablename__ = "module"
    name = Column(String)
    description = Column(String)
    role = relationship("Role", secondary="role_module", back_populates="modules", overlaps="permissions,role")
    tenant_profiles = relationship("TenantProfile", secondary="tenant_profile_module", back_populates="modules")
