from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from .infrastructure import FirmwareBase, SmartCameraProfileBase, SmartCameraProfileFirmwareInDB
from .region import CountrySchema, DistrictSchema, RegionSchema
from .wanted import WantedInDB


class TenantBase(BaseModel):
    name: str
    description: Optional[str] = None
    logo: Optional[str] = None
    tenant_profile_id: Optional[int] = None
    district_id: Optional[int] = None
    country_id: Optional[int] = None
    region_id: Optional[int] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    app_version: Optional[str] = None

    class Config:
        from_attributes = True


class TenantCreate(TenantBase):
    pass


class TenantUpdate(TenantBase):
    pass


class TenantInDBBase(TenantBase):
    id: int
    country: Optional[CountrySchema] = None
    region: Optional[RegionSchema] = None
    district: Optional[DistrictSchema] = None
    smart_camera_profiles: Optional[List[SmartCameraProfileBase]] = None
    firmwares: Optional[List[FirmwareBase]] = None
    wanteds: Optional[List[WantedInDB]] = None
    created_at: datetime
    updated_at: datetime


class SmartCameraProfileInDB(SmartCameraProfileBase):
    id: int
    tenant: TenantBase
    smart_camera_profile_firmwares: Optional[List[SmartCameraProfileFirmwareInDB]] = None
    created_at: datetime
    updated_at: datetime


class FirmwareInDB(FirmwareBase):
    id: int
    tenant: TenantBase
    created_at: datetime
    updated_at: datetime


class ScameraNoExistResponse(BaseModel):
    success: bool
    device_ids: Optional[List[str]] = None
    message: str


class GuessMessageData(BaseModel):
    name: str
    phone: str
    email: str | None = None
    description: str | None = None


class GuessInDB(GuessMessageData):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime
