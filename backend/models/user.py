from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String)
    phone = Column(String, nullable=True)
    photo = Column(String, nullable=True)
    user_group = Column(Integer, default=0, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"))
    role_id = Column(Integer, ForeignKey("role.id"))
    embedding = Column(String, nullable=True)
    cropped_image = Column(String, nullable=True)  # only image_url from minio
    embedding512 = Column(String, nullable=True)
    cropped_image512 = Column(String, nullable=True)
    pinfl = Column(String, nullable=True)
    pwd = Column(String)

    tenant_entity = relationship("TenantEntity", back_populates="users")
    role = relationship("Role", backref="users")
    activation_codes = relationship("UserActivationCode", back_populates="user")
    user_schedule_templates = relationship("UserScheduleTemplate", back_populates="user")
    errors = relationship("ErrorSmartCamera", back_populates="user")


class UserFCMToken(BaseModel):
    __tablename__ = "user_fcm_token"
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    device_id = Column(String)
    token = Column(String, nullable=False)
    app_version_code = Column(Integer)
    app_version_name = Column(String)
    device_name = Column(String)
    device_model = Column(String)


class UserActivationCode(BaseModel):
    __tablename__ = "user_activation_codes"
    user_id = Column(Integer, ForeignKey("users.id"))
    code = Column(String, nullable=False)
    user = relationship("User", back_populates="activation_codes")


class UserAttendance(BaseModel):
    __tablename__ = "user_attendance"
    ENTER = "enter"
    EXIT = "exit"
    ATTENDANCE_TYPES = [ENTER, EXIT]

    attendance_type = Column(String, default=ENTER)
    attendance_datetime = Column(DateTime)
    snapshot_url = Column(String, nullable=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    user = relationship("User")


class UserSmartCamera(BaseModel):
    __tablename__ = "user_smart_camera"
    user_id = Column(Integer, ForeignKey("users.id"))
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"))
    needs_tobe_updated = Column(Boolean, default=False)
    user = relationship("User")
    smart_camera = relationship("SmartCamera")
    UniqueConstraint(user_id, smart_camera_id)


class AccessToken(BaseModel):
    __tablename__ = "access_token"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, nullable=False)
    unique_id = Column(String, nullable=False, index=True)
    integrity_token = Column(String)
    app_version_code = Column(Integer)
    app_version_name = Column(String)
    device_id = Column(String)
    device_ip = Column(String)
    device_name = Column(String)
    device_model = Column(String)
    app_source = Column(String)
    refresh_id = Column(String, index=True)


class RefreshToken(BaseModel):
    __tablename__ = "refresh_token"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token = Column(String, nullable=False)
    refresh_id = Column(String, index=True)
