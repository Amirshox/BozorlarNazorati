import datetime
from typing import Optional

from pydantic import BaseModel

from schemas.role import RoleBase
from schemas.tenant_hierarchy_entity import TenantEntityInDBForUser


class UserBase(BaseModel):
    email: str
    first_name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    photo: Optional[str] = None
    user_group: Optional[int] = None
    embedding: Optional[str] = None
    cropped_image: Optional[str] = None
    embedding512: Optional[str] = None
    cropped_image512: Optional[str] = None
    pinfl: Optional[str] = None
    tenant_entity_id: int
    role_id: int


class UserCreate(UserBase):
    password: Optional[str] = None


class UserUpdate(UserBase):
    pass


class UserInDBBase(UserBase):
    id: int
    tenant_id: int
    role: Optional[RoleBase] = None
    tenant_entity: Optional[TenantEntityInDBForUser] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class UserActivationCodeBase(BaseModel):
    code: str
    user_id: int
    is_active: Optional[bool]


class UserSmartCameraBase(BaseModel):
    user_id: int
    smart_camera_id: int


class UserSmartCameraInDB(UserSmartCameraBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
