import datetime
from typing import Optional

from pydantic import BaseModel


class TenantAdminBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    password: Optional[str] = None
    photo: Optional[str] = None
    tenant_id: int


class TenantAdminCreate(TenantAdminBase):
    pass


class TenantAdminUpdate(TenantAdminBase):
    pass


class TenantAdminInDB(TenantAdminBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_active: bool

    class Config:
        from_attributes = True


class TenantAdminActivationCodeBase(BaseModel):
    code: str
    tenant_admin_id: int
    is_active: Optional[bool]


class TenantAdminBaseInActive(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    photo: Optional[str] = None
    tenant_id: int


class TenantAdminBaseCreateInActiveInDB(TenantAdminBaseInActive):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
