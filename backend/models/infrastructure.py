from sqlalchemy import Column, Float, Integer, String, and_, func, select
from sqlalchemy.orm import column_property, relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql.schema import ForeignKey

from models import IdentitySmartCamera
from models.base import BaseModel


class Building(BaseModel):
    __tablename__ = "building"
    name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"))

    tenant = relationship("Tenant")
    tenant_entity = relationship("TenantEntity", back_populates="buildings")


class Room(BaseModel):
    __tablename__ = "room"
    name = Column(String)
    description = Column(String)
    floor = Column(Integer)
    building_id = Column(Integer, ForeignKey("building.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"))

    __table_args__ = (UniqueConstraint("building_id", "name", name="room_building_id_name_key"),)


class Camera(BaseModel):
    __tablename__ = "camera"
    name = Column(String)
    description = Column(String)
    rtsp_url = Column(String)
    vpn_rtsp_url = Column(String)
    stream_url = Column(String)
    username = Column(String)
    password = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude = Column(Float)
    room_id = Column(Integer, ForeignKey("room.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"))
    status = Column(String, default="not_available")
    ip_address = Column(String, nullable=True)
    mac_address = Column(String, nullable=True)
    jetson_device_id = Column(Integer, ForeignKey("jetson_device.id"))

    rois = relationship("Roi", back_populates="camera")
    lines = relationship("Line", back_populates="camera")
    room = relationship("Room")
    tenant_entity = relationship("TenantEntity", back_populates="cameras")
    snapshots = relationship("CameraSnapshot", back_populates="camera")


class CameraSnapshot(BaseModel):
    __tablename__ = "camera_snapshot"
    snapshot_url = Column(String, nullable=True)
    camera_id = Column(Integer, ForeignKey("camera.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=True)
    snapshot_filename = Column(String)
    snapshot_bucketname = Column(String)

    camera = relationship("Camera", back_populates="snapshots")
    __table_args__ = (
        UniqueConstraint(
            "snapshot_url",
            "camera_id",
            name="camera_snapshot_snapshot_url_camera_id_key",
        ),
    )


class SmartCameraProfile(BaseModel):
    __tablename__ = "smart_camera_profile"
    name = Column(String)
    description = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))

    tenant = relationship("Tenant", back_populates="smart_camera_profiles")
    smart_camera_profile_firmwares = relationship("SmartCameraProfileFirmware", back_populates="profile")


class Firmware(BaseModel):
    __tablename__ = "firmware"
    name = Column(String)
    description = Column(String)
    img = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))

    tenant = relationship("Tenant", back_populates="firmwares")


class SmartCameraFirmware(BaseModel):
    __tablename__ = "smart_camera_firmware"
    firmware_id = Column(Integer, ForeignKey("firmware.id"))
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"))


class SmartCameraProfileFirmware(BaseModel):
    __tablename__ = "smart_camera_profile_firmware"
    profile_id = Column(Integer, ForeignKey("smart_camera_profile.id"))
    firmware_id = Column(Integer, ForeignKey("smart_camera_firmware.id"))

    profile = relationship("SmartCameraProfile", back_populates="smart_camera_profile_firmwares")


class SmartCamera(BaseModel):
    __tablename__ = "smart_camera"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    device_id = Column(String, index=True)
    device_mac = Column(String)
    lib_platform_version = Column(String)
    software_version = Column(String)
    lib_ai_version = Column(String)
    time_stamp = Column(Integer)
    device_name = Column(String)
    device_ip = Column(String)
    device_lat = Column(Float)
    device_long = Column(Float)
    device_type = Column(String)
    stream_url = Column(String)
    rtsp_url = Column(String)
    username = Column(String)
    password = Column(String)
    room_id = Column(Integer, ForeignKey("room.id"))
    type = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), index=True)
    smart_camera_profile_id = Column(Integer, ForeignKey("smart_camera_profile.id"))
    jetson_device_id = Column(Integer, ForeignKey("jetson_device.id"))
    temp_password = Column(String)
    last_snapshot_url = Column(String)

    rois = relationship("Roi", back_populates="smart_camera")
    lines = relationship("Line", back_populates="smart_camera")
    room = relationship("Room")
    tenant_entity = relationship("TenantEntity", back_populates="smart_cameras")
    snapshots = relationship("SmartCameraSnapshot", back_populates="smart_camera")

    identity_count = column_property(
        select(func.count(IdentitySmartCamera.id))
        .where(and_(IdentitySmartCamera.smart_camera_id == id))
        .correlate_except(IdentitySmartCamera)
        .scalar_subquery()
    )


class SmartCameraSnapshot(BaseModel):
    __tablename__ = "smart_camera_snapshot"
    snapshot_url = Column(String)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))

    smart_camera = relationship("SmartCamera", back_populates="snapshots")
    __table_args__ = (
        UniqueConstraint(
            "snapshot_url",
            "smart_camera_id",
            name="smart_camera_snapshot_snapshot_url_smart_camera_id_key",
        ),
    )


class BazaarSmartCameraSnapshot(BaseModel):
    __tablename__ = "bazaar_scamera_snapshot"
    snapshot_url = Column(String)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))


class JetsonDevice(BaseModel):
    __tablename__ = "jetson_device"
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)
    device_name = Column(String)
    device_id = Column(String)
    device_ip_vpn = Column(String)
    device_stream_url = Column(String)
    room_id = Column(Integer, ForeignKey("room.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))

    room = relationship("Room")
    profiles = relationship(
        "JetsonProfile",
        secondary="jetson_device_profile_association",
        back_populates="devices",
    )


class JetsonProfile(BaseModel):
    __tablename__ = "jetson_profile"
    name = Column(String)
    username = Column(String, unique=True)
    password = Column(String)
    cuda_version = Column(String)
    deepstream_version = Column(String)
    jetpack_version = Column(String)

    devices = relationship(
        "JetsonDevice",
        secondary="jetson_device_profile_association",
        back_populates="profiles",
    )


class JetsonDeviceProfileAssociation(BaseModel):
    __tablename__ = "jetson_device_profile_association"
    jetson_device_id = Column(Integer, ForeignKey("jetson_device.id"))
    jetson_profile_id = Column(Integer, ForeignKey("jetson_profile.id"))


class JetsonDeviceVPNCredentials(BaseModel):
    __tablename__ = "jetson_device_vpn_credentials"
    jetson_device_id = Column(Integer, ForeignKey("jetson_device.id"))
    client_certificate = Column(String, unique=True)
    client_key = Column(String, unique=True)
