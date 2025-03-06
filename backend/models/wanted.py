from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import BaseModel


class Wanted(BaseModel):
    __tablename__ = "wanted"
    first_name = Column(String)
    last_name = Column(String)
    photo = Column(String, nullable=False)
    phone = Column(String)
    pinfl = Column(String)
    concern_level = Column(Integer, default=1)  # min=1, max=10
    accusation = Column(String)
    description = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=True)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), nullable=True)

    tenant = relationship("Tenant", back_populates="wanteds")
    tenant_entity = relationship("TenantEntity", back_populates="wanteds")


class WantedSmartCamera(BaseModel):
    __tablename__ = "wanted_smart_camera"
    wanted_id = Column(Integer, ForeignKey("wanted.id"))
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"))
