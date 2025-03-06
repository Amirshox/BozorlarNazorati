from models.base import BaseModel
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, ForeignKey


class Role(BaseModel):
    __tablename__ = "role"
    name = Column(String)
    description = Column(String)
    code = Column(String)
    tenant_profile_id = Column(Integer, ForeignKey("tenant_profile.id"))
    modules = relationship("Module", secondary="role_module", back_populates="role", overlaps="role")
    permissions = relationship("RoleModule", back_populates="role", overlaps="modules")
    tenant_profile = relationship("TenantProfile", back_populates="roles")
