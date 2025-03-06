from typing import List, Optional
from sqlalchemy.orm import Session
from database import tenant_profile
from utils.pagination import CustomPage
from database.database import get_pg_db
from auth.oauth2 import get_current_sysadmin
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi import APIRouter, Depends, Security, HTTPException, status, Query
from schemas.tenant_profile import (
    TenantProfileInDBBase, TenantProfileCreate, TenantProfileUpdate, TenantProfileModuleBase,
    TenantProfileModuleCreate, TenantProfileModuleInDBBase, TenantProfileModuleList, TenantProfileWithRoleInDBBase
)

router = APIRouter(prefix='/tenant_profile', tags=['tenant_profile'])


@router.get('/', response_model=CustomPage[TenantProfileWithRoleInDBBase])
def get_tenant_profiles(
        is_active: Optional[bool] = Query(True, alias='is_active'),
        query: Optional[str] = Query(None, alias='query'),
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    query_set = tenant_profile.get_tenant_profiles(db, is_active, query)
    return paginate(query_set)


@router.post('/', response_model=TenantProfileInDBBase)
def create_tenant_profile(
        tenant_profile_data: TenantProfileCreate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return tenant_profile.create_tenant_profile(db, tenant_profile_data)


@router.get('/{pk}', response_model=TenantProfileInDBBase)
def get_tenant_profile(
        pk: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    tnt_profile = tenant_profile.get_tenant_profile(db, pk, is_active)
    if not tnt_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant Profile not found"
        )
    return tnt_profile


@router.put('/{pk}', response_model=TenantProfileInDBBase)
def update_tenant_profile(
        pk: int,
        tenant_profile_data: TenantProfileUpdate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return tenant_profile.update_tenant_profile(db, pk, tenant_profile_data)


@router.delete('/{pk}', response_model=TenantProfileInDBBase)
def delete_tenant_profile(
        pk: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return tenant_profile.delete_tenant_profile(db, pk)


@router.post('/module', response_model=TenantProfileModuleInDBBase)
def create_tenant_profile_module(
        tenant_profile_module_data: TenantProfileModuleCreate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return tenant_profile.create_tenant_profile_module(db, tenant_profile_module_data)


@router.post('/module/list', response_model=List[TenantProfileModuleBase])
def create_tenant_profile_modules_by_list(
        data: TenantProfileModuleList,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return tenant_profile.create_tenant_profile_modules_by_list(db, data)


@router.get('/module/{pk}', response_model=CustomPage[TenantProfileModuleInDBBase])
def get_tenant_profile_modules(
        pk: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    query_set = tenant_profile.get_modules_by_tenant_profile_id(db, pk)
    return paginate(query_set)
