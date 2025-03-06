from typing import Optional
from database import db_module
from sqlalchemy.orm import Session
from database.database import get_pg_db
from utils.pagination import CustomPage
from schemas.shared import ModuleInDBBase
from auth.oauth2 import get_current_sysadmin
from schemas.module import ModuleCreate, ModuleUpdate
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi import APIRouter, Depends, Security, Query

router = APIRouter(prefix='/module', tags=['module'])


@router.get('/', response_model=CustomPage[ModuleInDBBase])
def get_modules(
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    query_set = db_module.get_modules(db, is_active)
    return paginate(query_set)


@router.get('/{pk}', response_model=ModuleInDBBase)
def get_module(
        pk: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_module.get_module(db, pk, is_active)


@router.post('/', response_model=ModuleInDBBase)
def create_module(
        module: ModuleCreate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_module.create_module(db, module)


@router.put('/{pk}', response_model=ModuleInDBBase)
def update_module(
        pk: int,
        module: ModuleUpdate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_module.update_module(db, pk, module)


@router.delete('/{pk}', response_model=ModuleInDBBase)
def delete_module(
        pk: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_module.delete_module(db, pk)


@router.get('/tenant_profile/{tenant_profile_id}', response_model=CustomPage[ModuleInDBBase])
def get_modules_by_tenant_profile(
        tenant_profile_id: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    query_set = db_module.get_modules_by_tenat_profile_id(db, tenant_profile_id)
    return paginate(query_set)
