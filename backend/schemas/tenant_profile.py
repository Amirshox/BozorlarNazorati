import datetime
from typing import Optional, List

from pydantic import BaseModel

from .shared import ModuleInDBBase, RoleInDBBase


class TenantProfileBase(BaseModel):
    name: str
    description: Optional[str] = None


class TenantProfileCreate(TenantProfileBase):
    pass


class TenantProfileUpdate(TenantProfileBase):
    pass


class TenantProfileInDBBase(TenantProfileBase):
    id: int
    modules: Optional[List[ModuleInDBBase]] = None
    roles: Optional[List[RoleInDBBase]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RoleModulePermissions(BaseModel):
    name: str
    description: Optional[str] = None
    modules: Optional[List[ModuleInDBBase]] = None


class TenantProfileWithRoleInDBBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    roles: Optional[List[RoleInDBBase]] = None
    modules: Optional[List[ModuleInDBBase]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class TenantProfileModuleBase(BaseModel):
    tenant_profile_id: int
    module_id: int


class TenantProfileModuleList(BaseModel):
    tenant_profile_id: int
    modules: List[int]


class TenantProfileModuleCreate(TenantProfileModuleBase):
    pass


class TenantProfileModuleUpdate(TenantProfileModuleBase):
    pass


class TenantProfileModuleInDBBase(TenantProfileModuleBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    tenant_profile_id: int
    module_id: int
