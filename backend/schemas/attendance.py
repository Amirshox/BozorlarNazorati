from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .identity import IdentityInDBForAtts
from .wanted import WantedInDB


class AttendanceReportCreate(BaseModel):
    attendance_id: int
    description: str


class AttendanceReportBase(AttendanceReportCreate):
    status: str
    app_version_code: int | None = None
    app_version_name: str | None = None
    device_id: str | None = None
    device_ip: str | None = None
    device_name: str | None = None
    device_model: str | None = None


class AttendanceBase(BaseModel):
    attendance_type: str = "enter"
    attendance_datetime: datetime
    snapshot_url: Optional[str] = None
    background_image_url: Optional[str] = None
    body_image_url: Optional[str] = None
    identity_id: int
    tenant_id: Optional[int] = None
    tenant_entity_id: Optional[int] = None
    smart_camera_id: Optional[int] = None
    by_mobile: Optional[bool] = False
    bucket_name: Optional[str] = None
    object_name: Optional[str] = None
    position_id: Optional[int] = None
    embedding512: Optional[str] = None
    i_embedding512: Optional[str] = None
    device_ip: Optional[str] = None
    is_valid_recognition: Optional[bool] = True


class AttendanceCreate(BaseModel):
    identity_id: int
    image: str
    timestamp: int
    comp_score: Optional[float] = 0.0
    lat: Optional[float] = None
    lon: Optional[float] = None
    position_id: Optional[int] = None
    embedding512: Optional[str] = None
    i_embedding512: Optional[str] = None
    package_id: Optional[str] = None


class AttendanceAntiSpoofingInDB(BaseModel):
    id: int
    attendance_id: int
    is_spoofed: Optional[bool] = None
    score: Optional[float] = None
    real_score: Optional[float] = None
    fake_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PackageDetails(BaseModel):
    appRecognitionVerdict: str | None = None
    appLicensingVerdict: str | None = None
    deviceActivityLevel: str | None = None
    deviceRecognitionVerdict: str | None = None
    playProtectVerdict: str | None = None
    appsDetected: str | None = None
    request_nonce: str | None = None
    request_hash: str | None = None
    request_timestamp_millis: int | None = None

    class Config:
        from_attributes = True


class AttendanceInDB(AttendanceBase):
    id: int
    identity: IdentityInDBForAtts
    comp_score: Optional[float] = 0.0
    lat: Optional[float] = None
    lon: Optional[float] = None
    app_version_code: int | None = None
    app_version_name: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    device_model: str | None = None
    is_vm: Optional[bool] = None
    is_rooted: Optional[bool] = None
    is_valid_signature: Optional[bool] = None
    spoofing: Optional[AttendanceAntiSpoofingInDB] = None
    version: int | None = None
    has_warning: Optional[bool] = False
    package: Optional[PackageDetails] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class AttendanceSimilarityInArea(BaseModel):
    identity_id: int
    attendance_id: int | None = None
    image_url: str | None = None
    capture_timestamp: int | None = None
    similar_attendance_id: int | None
    similar_image_url: str | None = None
    similar_capture_timestamp: int | None
    distance: float | None = None
    created_at: datetime


class AttendanceSimilarityInEntity(BaseModel):
    identity_id: int
    tenant_entity_id: int | None = None
    attendance_id: int | None = None
    image_url: str | None = None
    capture_timestamp: int | None = None
    similar_attendance_id: int | None
    similar_image_url: str | None = None
    similar_capture_timestamp: int | None
    distance: float | None = None
    created_at: datetime


class SimilarityMainPhotoInArea(BaseModel):
    identity_id: int
    image_url: str | None = None
    version: int | None = None
    similar_identity_id: int | None
    similar_image_url: str | None = None
    similar_version: int | None = None
    distance: float | None = None


class SimilarityMainPhotoInEntity(BaseModel):
    identity_id: int
    tenant_entity_id: int | None = None
    image_url: str | None = None
    version: int | None = None
    similar_identity_id: int | None
    similar_image_url: str | None = None
    similar_tenant_entity_id: int | None = None
    similar_version: int | None = None
    distance: float | None = None


class AttendanceDetails(BaseModel):
    spoofing: Optional[AttendanceAntiSpoofingInDB] = None
    similarity_in_area: Optional[List[AttendanceSimilarityInArea]] = []
    similarity_in_entity: Optional[List[AttendanceSimilarityInEntity]] = []
    similarity_main_photo_in_area: Optional[List[SimilarityMainPhotoInArea]] = []
    similarity_main_photo_in_entity: Optional[List[SimilarityMainPhotoInEntity]] = []
    package: Optional[PackageDetails] = None


class AttendanceReportInDB(AttendanceReportBase):
    id: int
    user_id: int | None = None
    attendance: AttendanceInDB | None = None
    moderator_note: str | None = None
    version: int | None = None
    created_at: datetime
    updated_at: datetime


class IdentityForReportV2(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    photo: str | None = None

    class Config:
        from_attributes = True


class AttendanceForReportV2(BaseModel):
    id: int
    attendance_datetime: datetime
    snapshot_url: str | None = None
    device_name: str | None = None
    app_version_name: str | None = None
    identity: Optional[IdentityForReportV2] = None

    class Config:
        from_attributes = True


class AttendanceReportV2InDB(BaseModel):
    id: int
    status: str
    device_name: str | None = None
    app_version_name: str | None = None
    moderator_note: str | None = None
    attendance: Optional[AttendanceForReportV2] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AttendanceReportMini(AttendanceReportBase):
    id: int
    created_at: datetime
    updated_at: datetime


class MobileAttendanceInDB(AttendanceBase):
    id: int
    spoofing: AttendanceAntiSpoofingInDB | None = None
    version: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WantedAttendance(BaseModel):
    attendance_type: str
    attendance_datetime: datetime
    snapshot_url: Optional[str] = None
    background_image_url: Optional[str] = None
    body_image_url: Optional[str] = None
    wanted_id: int
    tenant_id: Optional[int] = None
    smart_camera_id: Optional[int] = None
    comp_score: Optional[float] = None


class WantedAttendanceInDB(WantedAttendance):
    id: int
    wanted: Optional[WantedInDB] = None
    created_at: datetime
    updated_at: datetime


class ExternalUserTokenResponse(BaseModel):
    success: bool
    token: str | None = None
