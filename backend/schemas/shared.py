import datetime
from typing import List, Optional

from pydantic import BaseModel


class ModuleBase(BaseModel):
    name: str
    description: str


class ModuleInDBBase(ModuleBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_profile_id: int


class RoleBaseInDB(RoleBase):
    id: int


class RoleModuleBase(BaseModel):
    role_id: int
    module_id: int
    read: Optional[bool] = False
    create: Optional[bool] = False
    update: Optional[bool] = False
    delete: Optional[bool] = False


class RoleModuleInDBBase(RoleModuleBase):
    id: int


class RoleInDBBase(RoleBase):
    id: int
    permissions: Optional[List[RoleModuleInDBBase]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
