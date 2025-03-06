from typing import List, Optional

from pydantic import BaseModel

from schemas.shared import RoleModuleBase


class RoleModuleCreate(RoleModuleBase):
    role_id: int
    module_id: int


class RoleModuleCreateByRole(RoleModuleBase):
    pass


class RoleModuleUpdate(RoleModuleBase):
    pass


class RoleModuleCreateByPermission(BaseModel):
    module_id: int
    read: Optional[bool] = False
    create: Optional[bool] = False
    update: Optional[bool] = False
    delete: Optional[bool] = False


class RoleModuleCreateByPermissions(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_profile_id: int
    permissions: List[RoleModuleCreateByPermission]
