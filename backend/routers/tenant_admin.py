from typing import Optional
from utils import generator
from sqlalchemy.orm import Session
from database.database import get_pg_db
from utils.pagination import CustomPage
from auth.oauth2 import get_current_sysadmin
from fastapi_pagination.ext.sqlalchemy import paginate
from database import db_tenant_admin, db_tenant_activation_code
from fastapi import APIRouter, Depends, Security, Query, HTTPException, status
from schemas.tenant_admin import (
    TenantAdminBase, TenantAdminCreate, TenantAdminUpdate, TenantAdminInDB, TenantAdminBaseCreateInActiveInDB,
    TenantAdminBaseInActive
)

router = APIRouter(prefix='/tenant_admin', tags=['tenant_admin'])


@router.get('/all/{tenant_id}', response_model=CustomPage[TenantAdminInDB])
def get_tenant_admins(
        tenant_id: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    query_set = db_tenant_admin.get_tenant_admins(db, tenant_id, is_active)
    return paginate(query_set)


@router.get('/{pk}', response_model=TenantAdminBase)
def get_tenant_admin(
        pk: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    tenant_admin = db_tenant_admin.get_tenant_admin_by_id(db, pk, is_active)
    if not tenant_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Tenant Admin not found'
        )
    return tenant_admin


@router.post('/', response_model=TenantAdminInDB)
def create_tenant_admin(
        tenant_admin: TenantAdminCreate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_tenant_admin.create_tenant_admin(db, tenant_admin)


@router.post('/create_in_active', response_model=TenantAdminBaseCreateInActiveInDB)
async def create_tenant_admin_in_active(
        tenant_admin: TenantAdminBaseInActive,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    in_active_tenant_admin = db_tenant_admin.create_inactive_tenant_admin(db, tenant_admin)
    activation_code = generator.generate_token(length=32)
    db_tenant_activation_code.create_tenant_admin_activation_code(db, activation_code, in_active_tenant_admin.id)
    return in_active_tenant_admin


@router.post('/activate')
def activate_tenant_platform(
        code: str,
        new_password: str,
        db: Session = Depends(get_pg_db)
):
    return db_tenant_activation_code.get_activation_code_and_update_password(db, code, new_password)


@router.put('/{pk}', response_model=TenantAdminInDB)
def update_tenant_admin(
        pk: int,
        tenant_admin: TenantAdminUpdate,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_tenant_admin.update_tenant_admin(db, pk, tenant_admin)


@router.delete('/{pk}', response_model=TenantAdminInDB)
def delete_tenant_admin(
        pk: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_tenant_admin.delete_tenant_admin(db, pk)
