from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .nvdsanalytics import ErrorSmartCameraInDB


class AttendanceAnalysis(BaseModel):
    total: int = 0
    above_threshold: int = 0
    below_threshold: int = 0
    percentage: float = 0


class IdentityBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic_name: Optional[str] = None
    photo: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pinfl: Optional[str] = None
    identity_group: Optional[int] = None
    identity_type: Optional[str] = None
    left_side_photo: Optional[str] = None
    right_side_photo: Optional[str] = None
    top_side_photo: Optional[str] = None
    embedding: Optional[str] = None
    cropped_image: Optional[str] = None
    embedding512: Optional[str] = None
    cropped_image512: Optional[str] = None
    external_id: Optional[str] = None
    jetson_device_id: Optional[int] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    i_embedding512: Optional[str] = None
    i_cropped_image512: Optional[str] = None
    recognisable_photo: Optional[str] = None
    metrics: Optional[str] = None

    class Config:
        from_attributes = True


class IdentityBase2(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    patronymic_name: Optional[str] = None
    photo: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pinfl: Optional[str] = None
    identity_group: Optional[int] = None
    identity_type: Optional[str] = None
    external_id: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    i_embedding512: Optional[str] = None
    i_cropped_image512: Optional[str] = None
    metrics: Optional[str] = None

    class Config:
        from_attributes = True


class IdentityBaseForRelative(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    patronymic_name: Optional[str] = None
    photo: Optional[str] = None
    identity_group: Optional[int] = None
    external_id: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None

    class Config:
        from_attributes = True


class IdentityBaseWithReceivedUrl(IdentityBase):
    recieved_photo_url: Optional[str] = None
    error: Optional[str] = None


class IdentityForSync(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    photo: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pinfl: Optional[str] = None
    identity_group: Optional[int] = None
    identity_type: Optional[str] = None
    external_id: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    id: Optional[int] = None


class ExtraAttendanceBase(BaseModel):
    id: int
    identity_id: int
    position_id: int | None = None
    position_name: str | None = None
    week_day: int | None = None
    start_time: str | None = None
    end_time: str | None = None

    class Config:
        from_attributes = True


class IdentityPhotoBase(BaseModel):
    id: int
    url: str
    embedding: str | None = None
    cropped_image: str | None = None
    embedding512: str | None = None
    cropped_image512: str | None = None
    i_embedding512: str | None = None
    i_cropped_image512: str | None = None
    created_at: datetime
    version: Optional[int] = None
    photo_id: Optional[str] = None
    passport_verification_result: Optional[bool] = None

    class Config:
        from_attributes = True


class IdentitySelect(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    patronymic_name: Optional[str] = None
    photo: Optional[str] = None
    pinfl: Optional[str] = None
    identity_group: Optional[int] = None
    identity_type: Optional[str] = None
    embedding: Optional[str] = None
    cropped_image: Optional[str] = None
    embedding512: Optional[str] = None
    i_embedding512: Optional[str] = None
    cropped_image512: Optional[str] = None
    i_cropped_image512: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    recognisable_photo: Optional[str] = None
    passport_verification_result: Optional[int] = 0  # 0 - None, 1 - True, 2 - False
    tenant_entity_id: int
    extra_attendances: Optional[List[ExtraAttendanceBase]] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    version: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class IdentitySelectWithPhotos(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    patronymic_name: Optional[str] = None
    photo: Optional[str] = None
    pinfl: Optional[str] = None
    identity_group: Optional[int] = None
    identity_type: Optional[str] = None
    embedding: Optional[str] = None
    cropped_image: Optional[str] = None
    embedding512: Optional[str] = None
    i_embedding512: Optional[str] = None
    cropped_image512: Optional[str] = None
    i_cropped_image512: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    recognisable_photo: Optional[str] = None
    passport_verification_result: Optional[int] = 0  # 0 - None, 1 - True, 2 - False
    tenant_entity_id: int
    extra_attendances: Optional[List[ExtraAttendanceBase]] = None
    photos: Optional[List[IdentityPhotoBase]] = []
    lat: Optional[float] = None
    lon: Optional[float] = None
    version: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class IdentityCreate(IdentityBase):
    tenant_entity_id: int


class IdentityUpdate(IdentityBase):
    signature: str | None = None


class IdentitySmartCameraBase(BaseModel):
    identity_id: int
    smart_camera_id: int


class IdentitySmartCameraCreate(BaseModel):
    identity_id: int
    smart_camera_id_list: Optional[List[int]] = None
    tenant_entity_id: Optional[int] = None


class IdentitySmartCameraInDB(IdentitySmartCameraBase):
    id: int
    version: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class IdentityPhotoBaseForPlaton(BaseModel):
    id: int
    url: str
    created_at: datetime
    version: Optional[int] = None
    photo_id: Optional[str] = None

    class Config:
        from_attributes = True


class IdentityBaseForPlaton(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    patronymic_name: Optional[str] = None
    photo: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pinfl: Optional[str] = None
    identity_group: Optional[int] = None
    identity_type: Optional[str] = None
    external_id: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    version: Optional[int] = 1
    photos: Optional[List[IdentityPhotoBaseForPlaton]] = None

    class Config:
        from_attributes = True


class RelativeBase(BaseModel):
    first_name: str
    last_name: str | None = None
    photo: str | None = None
    email: str | None = None
    phone: str | None = None
    pinfl: str | None = None

    class Config:
        from_attributes = True


class RelativeCreate(RelativeBase):
    kid_ids: List[int] | None = None
    error: str | None = None


class IdentityRelativeBase(BaseModel):
    identity_id: int
    relative_id: int


class RelativeInDB(RelativeBase):
    id: int
    identities: List[IdentityRelativeBase] | None = None
    created_at: datetime
    updated_at: datetime
    is_active: bool


class IdentityRelativeInDB(IdentityRelativeBase):
    id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool


class TenantEntityIdName(BaseModel):
    id: int
    name: str
    external_id: int | None = None

    class Config:
        from_attributes = True


class TenantEntityForRelativeBase(TenantEntityIdName):
    kassa_id: Optional[str] = None

    class Config:
        from_attributes = True


class IdentityInDBForRelative(IdentityBase):
    id: int
    tenant_entity: TenantEntityForRelativeBase | None = None
    version: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class IdentityInDB(IdentityBase):
    id: int
    tenant_entity: TenantEntityIdName | None = None
    errors: Optional[List[ErrorSmartCameraInDB]] = None
    identity_smart_cameras: Optional[List[IdentitySmartCameraBase]] = None
    photos: Optional[List[IdentityPhotoBase]] = None
    extra_attendances: Optional[List[ExtraAttendanceBase]] = None
    passport_verification_result: Optional[bool] = None
    version: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class IdentityInDBForAtts(IdentityBase2):
    id: int
    tenant_entity: TenantEntityIdName | None = None
    version: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class CheckIdentitySmartCamera(BaseModel):
    image: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius: Optional[float] = None
    district: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None


class SimpleResponse(BaseModel):
    success: bool
    message: str | None = None


class ParentAttendanceScheme(BaseModel):
    relative: RelativeBase
    snapshot_url: str
    date: str
    identities: List[IdentityBaseForRelative] | None = None

    class Config:
        from_attributes = True


class PackageBase(BaseModel):
    attendance_count: int
    identity_ids: List[int]
    integrity_token: str
    appRecognitionVerdict: str | None = None
    appLicensingVerdict: str | None = None
    deviceActivityLevel: str | None = None
    deviceRecognitionVerdict: str | None = None
    playProtectVerdict: str | None = None
    request_nonce: str | None = None
    request_hash: str | None = None
    request_timestamp_millis: int | None = None
    appsDetected: str | None = None


class PackageResponse(PackageBase):
    id: int
    uuid: str
    tenant_id: int | None = None
    tenant_entity_id: int
    created_at: datetime


class AppDetailsData(BaseModel):
    package_name: str | None = None
    app_name: str | None = None
    app_icon: str | None = None
    app_version_name: str | None = None
    app_version_code: int | None = None
    requested_permissions: List[str] | None = None
    install_location: str | None = None
    state: bool | None = None


class MetricsSeriaBase(BaseModel):
    id: int
    name: str


class NotificationBase(BaseModel):
    sender_id: int
    sender_type: str | None = None
    receiver_id: int
    receiver_type: str | None = None
    title: str | None = None
    body: str | None = None
    data: dict | None = None
    type_index: int
    is_sent_via_one_system: bool
    is_sent_via_platon: bool
    attempt_count: int


class NotificationInDB(NotificationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CustomLocationInDB(BaseModel):
    id: int
    user_id: int
    lat: float
    lon: float
    description: str | None = None
    app_version_code: int | None = None
    app_version_name: str | None = None
    device_id: str | None = None
    device_name: str | None = None
    device_model: str | None = None
    tenant_entity_id: int | None = None
    created_at: datetime


class IdentityPhotoForLabeling(BaseModel):
    id: int
    url: str
    created_at: datetime
    version: Optional[int] = None
    passport_verification_result: Optional[bool] = None

    class Config:
        from_attributes = True


class TenantEntityForLabelingStatus(BaseModel):
    id: int
    name: str
    external_id: int | None = None


class IdentityLabelingStatus(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    labeling_status: int | None = None
    tenant_entity: TenantEntityForLabelingStatus | None = None


class IdentityLabelingStatusResponse(BaseModel):
    items: List[IdentityLabelingStatus] | None = None
    total: int
    page: int
    size: int
    pages: int
    unchecked: int | None = 0
    checked: int | None = 0
    changed: int | None = 0
