import uuid

from sqlalchemy import ARRAY, BigInteger, Boolean, Column, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class Identity(BaseModel):
    __tablename__ = "identity"
    first_name = Column(String)
    last_name = Column(String)
    patronymic_name = Column(String)
    photo = Column(String)
    email = Column(String)
    phone = Column(String)
    pinfl = Column(String)
    identity_group = Column(Integer, default=0)
    identity_type = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), index=True)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), index=True)
    version = Column(Integer, default=1)
    left_side_photo = Column(String)
    right_side_photo = Column(String)
    top_side_photo = Column(String)
    recieved_photo_url = Column(String)
    embedding = Column(String)
    cropped_image = Column(String)  # only image_url from minio
    embedding512 = Column(String)
    cropped_image512 = Column(String)  # only image_url from minio
    external_id = Column(String, index=True)
    jetson_device_id = Column(Integer, ForeignKey("jetson_device.id"), nullable=True, index=True)
    group_id = Column(Integer)
    group_name = Column(String)
    bucket_name = Column(String)
    object_name = Column(String, index=True)
    i_embedding512 = Column(String)
    i_cropped_image512 = Column(String)  # only image_url from minio
    metrics = Column(String)
    lat = Column(Float)
    lon = Column(Float)
    deleted = Column(Boolean, default=False)
    labeling_status = Column(Integer, default=1)
    recognisable_photo = Column(String)
    approved_at = Column(String)
    dismissed_at = Column(String)

    tenant = relationship("Tenant")
    tenant_entity = relationship("TenantEntity", back_populates="identities")
    identity_smart_cameras = relationship("IdentitySmartCamera", back_populates="identity")
    errors = relationship("ErrorSmartCamera", back_populates="identity")
    photos = relationship("IdentityPhoto", back_populates="identity")
    extra_attendances = relationship("ExtraAttendance", back_populates="identity")


class IdentityPhoto(BaseModel):
    __tablename__ = "identity_photo"
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=False, index=True)
    url = Column(String)
    embedding = Column(String)
    cropped_image = Column(String)
    embedding512 = Column(String)
    cropped_image512 = Column(String)
    i_embedding512 = Column(String)
    i_cropped_image512 = Column(String)
    version = Column(Integer, default=1)
    photo_id = Column(String)
    passport_verification_result = Column(Boolean, default=True)
    labeled = Column(Boolean, default=False)

    identity = relationship("Identity", back_populates="photos")


class UpdateIdentity(BaseModel):
    __tablename__ = "update_identity"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=False, index=True)
    version = Column(Integer)
    app_version_code = Column(Integer)
    app_version_name = Column(String)
    device_id = Column(String)
    device_ip = Column(String)
    device_name = Column(String)
    device_model = Column(String)
    verified_by = Column(Integer, default=-1)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), nullable=True, index=True)


class CustomLocation(BaseModel):
    __tablename__ = "custom_location"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lat = Column(Float)
    lon = Column(Float)
    description = Column(Text)
    app_version_code = Column(Integer)
    app_version_name = Column(String)
    device_id = Column(String)
    device_name = Column(String)
    device_model = Column(String)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), nullable=True, index=True)


class Attendance(BaseModel):
    __tablename__ = "attendance"
    attendance_type = Column(String, default="enter")
    attendance_datetime = Column(DateTime)
    snapshot_url = Column(String)
    background_image_url = Column(String)
    body_image_url = Column(String)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), index=True)
    identity_id = Column(Integer, ForeignKey("identity.id"), index=True)
    comp_score = Column(Float)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), index=True)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), nullable=True, index=True)
    by_mobile = Column(Boolean, default=False)
    lat = Column(Float)
    lon = Column(Float)
    app_version_code = Column(Integer)
    app_version_name = Column(String)
    device_id = Column(String)
    device_name = Column(String)
    device_model = Column(String)
    device_ip = Column(String)
    is_vm = Column(Boolean)
    is_rooted = Column(Boolean)
    is_valid_signature = Column(Boolean)
    is_valid_recognition = Column(Boolean, default=True)
    bucket_name = Column(String)
    object_name = Column(String)
    position_id = Column(Integer, index=True)
    embedding512 = Column(String)
    version = Column(Integer, default=1)
    package_id = Column(Integer, ForeignKey("package.id"), nullable=True, index=True)
    package_uuid = Column(String, index=True)
    has_warning = Column(Boolean, default=False)
    i_embedding512 = Column(String)
    account_licensing_verdict = Column(String)
    mismatch_entity = Column(Boolean, default=False)
    token_id = Column(String, index=True)
    attestation_id = Column(Integer, index=True)
    username = Column(String)
    app_source = Column(String)

    identity = relationship("Identity")
    spoofing = relationship("AttendanceAntiSpoofing", back_populates="attendance", uselist=False)
    report = relationship("AttendanceReport", back_populates="attendance")
    package = relationship("Package", back_populates="attendance")


class WantedAttendance(BaseModel):
    __tablename__ = "wanted_attendance"
    attendance_type = Column(String)
    attendance_datetime = Column(DateTime)
    snapshot_url = Column(String)
    background_image_url = Column(String)
    body_image_url = Column(String)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), index=True)
    wanted_id = Column(Integer, ForeignKey("wanted.id"), index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), index=True)
    comp_score = Column(Float)

    wanted = relationship("Wanted")


class IdentitySmartCamera(BaseModel):
    __tablename__ = "identity_smart_camera"
    identity_id = Column(Integer, ForeignKey("identity.id"), index=True)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), index=True)
    version = Column(Integer, default=1)
    needs_tobe_updated = Column(Boolean, default=False)

    identity = relationship("Identity", back_populates="identity_smart_cameras")
    __table_args__ = (
        UniqueConstraint(
            "identity_id", "smart_camera_id", name="identity_smart_camera_identity_id_smart_camera_id_key"
        ),
    )


class AttendanceAntiSpoofing(BaseModel):
    __tablename__ = "attendance_anti_spoofing"
    attendance_id = Column(Integer, ForeignKey("attendance.id"), index=True)
    is_spoofed = Column(Boolean)
    score = Column(Float)
    real_score = Column(Float)
    fake_score = Column(Float)

    attendance = relationship("Attendance", back_populates="spoofing")


class Relative(BaseModel):
    __tablename__ = "relative"
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    full_name = Column(String)

    photo = Column(String)
    email = Column(String)
    phone = Column(String)
    address = Column(String)
    gender = Column(Integer)

    pinfl = Column(String, unique=True)
    passport_serial = Column(String)
    birth_date = Column(Date)

    username = Column(String, unique=True)
    password = Column(String)

    tin = Column(Integer)
    patronymic_name = Column(String)
    region_id = Column(Integer)  # external
    district_id = Column(Integer)  # external
    passport_given_place = Column(String)
    passport_date_begin = Column(String)
    passport_date_end = Column(String)

    pwd = Column(String)

    identities = relationship("IdentityRelative", back_populates="relatives")
    attendances = relationship("RelativeAttendance", back_populates="relative", lazy="noload")

    def __repr__(self):
        return f"<Relative: {self.first_name} {self.last_name}>"


class RelativeFCMToken(BaseModel):
    __tablename__ = "relative_fcm_token"
    relative_id = Column(Integer, ForeignKey("relative.id"), index=True)
    device_id = Column(String)
    token = Column(String, nullable=False)


class RelativeSmartCamera(BaseModel):
    __tablename__ = "relative_smart_camera"
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=False, index=True)
    relative_id = Column(Integer, ForeignKey("relative.id"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("relative_id", "smart_camera_id", name="relative_smart_camera_id_key"),)


class IdentityRelative(BaseModel):
    __tablename__ = "identity_relative"
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=False, index=True)
    relative_id = Column(Integer, ForeignKey("relative.id"), nullable=False, index=True)

    relatives = relationship("Relative", back_populates="identities")


class RelativeAttendance(BaseModel):
    __tablename__ = "relative_attendance"
    attendance_type = Column(String)
    attendance_datetime = Column(DateTime)
    snapshot_url = Column(String, nullable=True)
    relative_id = Column(Integer, ForeignKey("relative.id"), index=True)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), index=True)
    comp_score = Column(Float, nullable=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), nullable=True, index=True)

    relative = relationship("Relative", back_populates="attendances")


class AttendanceReport(BaseModel):
    __tablename__ = "attendance_report"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=False, index=True)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), nullable=True, index=True)
    description = Column(String, nullable=False)
    status = Column(String, default="IN_PROGRESS")
    version = Column(Integer, default=1)
    app_version_code = Column(Integer)
    app_version_name = Column(String)
    device_id = Column(String)
    device_ip = Column(String)
    device_name = Column(String)
    device_model = Column(String)
    moderator_note = Column(String)

    attendance = relationship("Attendance", back_populates="report")


class ErrorRelativeSmartCamera(BaseModel):
    __tablename__ = "error_relative_smart_camera"
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=False, index=True)
    relative_id = Column(Integer, ForeignKey("relative.id"), nullable=False, index=True)
    code = Column(Integer)
    text = Column(String)


class ExtraAttendance(BaseModel):
    __tablename__ = "extra_attendance"
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=False, index=True)
    position_id = Column(Integer)
    position_name = Column(String)
    week_day = Column(Integer)
    start_time = Column(String)
    end_time = Column(String)

    identity = relationship("Identity", back_populates="extra_attendances")


class Package(BaseModel):
    __tablename__ = "package"
    uuid = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    attendance_count = Column(Integer)
    identity_ids = Column(ARRAY(Integer), default=lambda: [])
    integrity_token = Column(String)
    appRecognitionVerdict = Column(String)
    appLicensingVerdict = Column(String)
    deviceActivityLevel = Column(String)
    deviceRecognitionVerdict = Column(String)
    playProtectVerdict = Column(String)
    request_nonce = Column(String)
    request_hash = Column(String)
    request_timestamp_millis = Column(BigInteger)
    appsDetected = Column(String)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), index=True)
    tenant_id = Column(Integer, ForeignKey("tenant.id"), index=True)

    attendance = relationship("Attendance", back_populates="package")


class AppDetail(BaseModel):
    __tablename__ = "app_detail"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(String, nullable=False, index=True)
    package_name = Column(String)
    app_name = Column(String)
    app_icon = Column(String)
    app_version_name = Column(String)
    app_version_code = Column(Integer)
    requested_permissions = Column(ARRAY(String), default=lambda: [])
    install_location = Column(String)
    state = Column(Boolean)


class MetricsSeria(BaseModel):
    __tablename__ = "metrics_seria"
    name = Column(String, nullable=False)
