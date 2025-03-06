from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class Tenant(BaseModel):
    __tablename__ = "tenant"
    name = Column(String)
    description = Column(String)
    logo = Column(String)
    zip_code = Column(String)
    phone = Column(String)
    email = Column(String)
    website = Column(String)
    country_id = Column(Integer, ForeignKey("country.id"))
    region_id = Column(Integer, ForeignKey("region.id"))
    district_id = Column(Integer, ForeignKey("district.id"))
    tenant_profile_id = Column(Integer, ForeignKey("tenant_profile.id"))
    app_version = Column(String)

    tenant_profile = relationship("TenantProfile")
    country = relationship("Country")
    region = relationship("Region")
    district = relationship("District", back_populates="tenants")
    smart_camera_profiles = relationship("SmartCameraProfile", back_populates="tenant")
    firmwares = relationship("Firmware", back_populates="tenant")
    wanteds = relationship("Wanted", back_populates="tenant")


class GuessMessage(BaseModel):
    __tablename__ = "guess_message"
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    email = Column(String)
    description = Column(String)
    status = Column(String, default="NEW")  # ['NEW', 'ARCHIVED', 'SELECTED']
