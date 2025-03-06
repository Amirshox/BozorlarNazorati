from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    and_,
    func,
    select,
)
from sqlalchemy.orm import column_property, relationship

from models import Identity, SmartCamera
from models.base import BaseModel


class TenantEntity(BaseModel):
    __tablename__ = "tenant_entity"
    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("tenant_entity.id"), nullable=True)
    name = Column(String, nullable=False)
    photo = Column(String)
    description = Column(String)
    district_id = Column(Integer, ForeignKey("district.id"))
    country_id = Column(Integer, ForeignKey("country.id"))
    region_id = Column(Integer, ForeignKey("region.id"))
    tenant_id = Column(Integer, nullable=False)
    hierarchy_level = Column(Integer, nullable=False)
    trackable = Column(Boolean, default=False)
    blacklist_monitoring = Column(Boolean, default=False)
    external_id = Column(Integer, nullable=True)
    lat = Column(Float)
    lon = Column(Float)
    mahalla_code = Column(Integer)
    tin = Column(String)
    phone = Column(String)
    director_name = Column(String)
    director_pinfl = Column(String)
    director_image = Column(String)
    ignore_location_restriction = Column(Boolean, default=False)
    kassa_id = Column(String)

    users = relationship("User", back_populates="tenant_entity")
    identities = relationship("Identity", back_populates="tenant_entity", lazy="noload")
    smart_cameras = relationship("SmartCamera", back_populates="tenant_entity")
    buildings = relationship("Building", back_populates="tenant_entity")
    country = relationship("Country")
    region = relationship("Region")
    district = relationship("District", back_populates="tenant_entities")
    wanteds = relationship("Wanted", back_populates="tenant_entity")
    cameras = relationship("Camera", back_populates="tenant_entity")
    children = relationship(
        "TenantEntity", back_populates="parent", remote_side="TenantEntity.id"
    )  # Use 'TenantEntity.id' directly

    # mobile configuration
    allowed_radius = Column(Integer)
    face_auth_threshold = Column(Float)
    spoofing_threshold = Column(Float)
    signature_key = Column(String)
    is_light = Column(Boolean)

    parent = relationship(
        "TenantEntity",
        remote_side="TenantEntity.parent_id",  # Use 'TenantEntity.parent_id' directly
        back_populates="children",
    )

    identity_count = column_property(
        select(func.count(Identity.id))
        .where(and_(Identity.tenant_entity_id == id, Identity.is_active))
        .correlate_except(Identity)
        .scalar_subquery()
    )

    smart_camera_count = column_property(
        select(func.count(SmartCamera.id))
        .where(and_(SmartCamera.tenant_entity_id == id, SmartCamera.is_active))
        .correlate_except(SmartCamera)
        .scalar_subquery()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "external_id", name="tenant_entity_tenant_id_external_id_key"),)
