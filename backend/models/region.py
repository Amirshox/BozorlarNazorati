from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class Country(BaseModel):
    __tablename__ = "country"
    name = Column(String, unique=True, nullable=False)

    regions = relationship("Region", back_populates="country")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
        }


class Region(BaseModel):
    __tablename__ = "region"
    name = Column(String, unique=True, nullable=False)
    country_id = Column(Integer, ForeignKey("country.id"), nullable=False)

    country = relationship("Country", back_populates="regions")
    districts = relationship("District", back_populates="region")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "country_id": self.country_id,
        }


class District(BaseModel):
    __tablename__ = "district"
    name = Column(String, unique=True, nullable=False)
    country_id = Column(Integer, ForeignKey("country.id"), nullable=True)
    region_id = Column(Integer, ForeignKey("region.id"), nullable=False)
    external_id = Column(Integer)

    region = relationship("Region", back_populates="districts")
    country = relationship("Country")
    tenant_entities = relationship("TenantEntity", back_populates="district")
    tenants = relationship("Tenant", back_populates="district")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "region_id": self.region_id,
            "country_id": self.country_id,
        }
