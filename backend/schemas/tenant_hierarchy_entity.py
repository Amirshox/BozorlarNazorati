from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .region import CountrySchema, DistrictSchema, RegionSchema
from .wanted import WantedInDB


class TenantEntityBase(BaseModel):
    parent_id: Optional[int] = None
    name: str
    photo: Optional[str] = None
    description: Optional[str] = None
    district_id: int
    region_id: Optional[int] = None
    country_id: Optional[int] = None
    hierarchy_level: int
    trackable: Optional[bool] = False
    blacklist_monitoring: Optional[bool] = False
    external_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    mahalla_code: Optional[int] = None
    tin: Optional[str] = None
    phone: Optional[str] = None
    director_name: Optional[str] = None
    director_pinfl: Optional[str] = None
    director_image: Optional[str] = None
    ignore_location_restriction: Optional[bool] = False

    # mobile configuration
    allowed_radius: Optional[int] = None
    face_auth_threshold: Optional[float] = None
    spoofing_threshold: Optional[float] = None
    signature_key: Optional[str] = None
    is_light: Optional[bool] = None
    # server_time: Optional[int] = None

    # @validator("server_time", always=True)
    # def get_server_time(cls, v, values):
    #     server_time = values.get("server_time")  # noqa
    #     return int(datetime.now().timestamp())


class TenantEntityCreate(TenantEntityBase):
    pass


class TenantEntityUpdate(BaseModel):
    parent_id: Optional[int] = None
    name: Optional[str] = None
    photo: Optional[str] = None
    description: Optional[str] = None
    district_id: Optional[int] = None
    region_id: Optional[int] = None
    country_id: Optional[int] = None
    hierarchy_level: Optional[int] = None
    trackable: Optional[bool] = False
    blacklist_monitoring: Optional[bool] = False
    external_id: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    mahalla_code: Optional[int] = None
    tin: Optional[str] = None
    phone: Optional[str] = None
    director_name: Optional[str] = None
    director_pinfl: Optional[str] = None
    director_image: Optional[str] = None
    ignore_location_restriction: Optional[bool] = False

    # mobile configuration
    allowed_radius: Optional[int] = None
    face_auth_threshold: Optional[float] = None
    spoofing_threshold: Optional[float] = None
    signature_key: Optional[str] = None
    is_light: Optional[bool] = None


class TenantEntityInDBForUser(TenantEntityBase):
    id: int
    district: Optional[DistrictSchema] = None
    identity_count: Optional[int] = None
    smart_camera_count: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class EntityGroup(BaseModel):
    group_id: int
    group_name: str | None = None
    lat: float | None = None
    lon: float | None = None

    class Config:
        from_attributes = True


class TenantEntityInDB(TenantEntityBase):
    id: int
    tenant_id: int
    country: Optional[CountrySchema] = None
    region: Optional[RegionSchema] = None
    district: Optional[DistrictSchema] = None
    wanteds: Optional[List[WantedInDB]] = None
    identity_count: Optional[int] = None
    smart_camera_count: Optional[int] = None
    groups: Optional[List[EntityGroup]] = None
    created_at: datetime
    updated_at: datetime


class TenantEntityMobileConfigurations(BaseModel):
    allowed_radius: Optional[int] = None
    face_auth_threshold: Optional[float] = None
    spoofing_threshold: Optional[float] = None
    signature_key: Optional[str] = None
    is_light: Optional[bool] = None
    ignore_location_restriction: Optional[bool] = False


class TenantEntityFilteredDetails(BaseModel):
    id: int
    name: Optional[str] = None
    external_id: Optional[int] = None
    allowed_radius: Optional[int] = None
    face_auth_threshold: Optional[float] = None
    spoofing_threshold: Optional[float] = None
    signature_key: Optional[str] = None
    ignore_location_restriction: Optional[bool] = None
    lon: Optional[float] = None
    lat: Optional[float] = None

    smart_camera_count: Optional[int] = None
    room_count: Optional[int] = None
    building_count: Optional[int] = None


class TenantEntityCreateExternal(BaseModel):
    name: str
    district_code: int
    external_id: int
    lat: float | None = None
    lon: float | None = None
    mahalla_code: Optional[int] = None
    tin: Optional[str] = None
    phone: Optional[str] = None
    director_name: Optional[str] = None
    director_pinfl: Optional[str] = None
    director_image: Optional[str] = None


class TenantEntityCreateExternalSuccess(BaseModel):
    id: int
    external_id: int


class TenantEntityCreateExternalError(BaseModel):
    entity: TenantEntityCreateExternal
    error: str


class TenantEntityCreateListResponse(BaseModel):
    total_count: int
    created_list: List[TenantEntityCreateExternalSuccess] | None = None
    error_count: int
    error_list: List[TenantEntityCreateExternalError] | None = None


class SmartCameraBaseForFilter(BaseModel):
    id: int
    name: str
    device_id: Optional[str] = None
    type: Optional[str] = None


class EntityForFilter(BaseModel):
    id: int
    name: str
    region: RegionSchema
    district: DistrictSchema
    smart_cameras: Optional[List[SmartCameraBaseForFilter]] = None

    class Config:
        from_attributes = True


class TenantEntityAttendanceAnalytics(BaseModel):
    tenant_entity_id: Optional[int] = None
    tenant_entity_name: Optional[str] = None
    external_id: Optional[int] = None
    kids_attendance_count: Optional[int] = None
    employees_attendance_count: Optional[int] = None
    kids_total_count: Optional[int] = None
    employees_total_count: Optional[int] = None
    attendance_ratio: Optional[float] = None


class MttCompareAttendanceCount(BaseModel):
    id: int
    mtt_id: int
    name: str
    total_count: int
    kids_count: int
    employees_count: int
    total_kids: int
    accepted_kids: int
    rejected_kids: int
    waiting_kids: int
    total_edus: int
    accepted_edus: int
    rejected_edus: int
    waiting_edus: int


class TotalCountSchema(BaseModel):
    entity: int
    area: int


class SimilarityBase(BaseModel):
    identity_id: int
    first_name: str | None = None
    last_name: str | None = None
    version: int | None = None
    pinfl: str | None = None
    image_url: str | None = None
    tenant_entity_name: str | None = None


class SimilarityItemBase(BaseModel):
    id: int
    similar_identity_id: int
    similar_identity_first_name: str | None = None
    similar_identity_last_name: str | None = None
    similar_tenant_entity_id: int | None = None
    similar_entity_name: str | None = None
    similar_version: int | None = None
    distance: float | None = None
    similar_image_url: str | None = None
    created_at: datetime


class AreaSimilarityBase(SimilarityBase):
    similarities: List[SimilarityItemBase] | None = []


class EntitySimilarityBase(SimilarityBase):
    tenant_entity_id: int | None = None
    similarities: List[SimilarityItemBase] | None = []


class SimilarIdentityInAreaResponse(BaseModel):
    items: List[AreaSimilarityBase] | None = []
    total: int
    page: int
    size: int


class SimilarIdentityInEntityResponse(BaseModel):
    items: List[EntitySimilarityBase] | None = []
    total: int
    page: int
    size: int
