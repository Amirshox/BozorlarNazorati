from typing import Optional

from fastapi import APIRouter, Depends, Query, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_sysadmin
from database import db_role_module
from database.database import get_pg_db
from schemas.role_module import RoleModuleCreate, RoleModuleCreateByPermissions, RoleModuleUpdate
from schemas.shared import RoleInDBBase, RoleModuleInDBBase
from utils.pagination import CustomPage

router = APIRouter(prefix="/role_module_permission", tags=["role_module_permission"])


@router.get("/", response_model=CustomPage[RoleModuleInDBBase])
def get_role_modules(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    query_set = db_role_module.get_role_modules(db, is_active)
    return paginate(query_set)


@router.get("/{pk}", response_model=RoleModuleInDBBase)
def get_role_module(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return db_role_module.get_role_module(db, pk, is_active)


@router.post("/", response_model=RoleModuleInDBBase)
def create_role_module(
    role_module: RoleModuleCreate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)
):
    return db_role_module.create_role_module(db, role_module)


@router.put("/{pk}", response_model=RoleModuleInDBBase)
def update_role_module(
    pk: int, role_module: RoleModuleUpdate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)
):
    return db_role_module.update_role_module(db, pk, role_module)


@router.delete("/{pk}", response_model=RoleModuleInDBBase)
def delete_role_module(pk: int, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db_role_module.delete_role_module(db, pk)


@router.post("/by_permission_list", response_model=RoleInDBBase)
def create_role_by_permission_list(
    data: RoleModuleCreateByPermissions, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)
):
    return db_role_module.create_role_module_by_permissions(db, data)


@router.put("/by_permission_list/{pk}", response_model=RoleInDBBase)
def update_role_by_permission_list(
    pk: int,
    data: RoleModuleCreateByPermissions,
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return db_role_module.update_role_module_by_permissions(db, pk, data)
