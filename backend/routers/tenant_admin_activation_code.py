from sqlalchemy.orm import Session
from utils.pagination import CustomPage
from database.database import get_pg_db
from auth.oauth2 import get_current_sysadmin
from database import db_tenant_activation_code
from fastapi import APIRouter, Depends, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from schemas.tenant_admin import TenantAdminActivationCodeBase


router = APIRouter(prefix='/tenant_admin_activation_code', tags=['tenant_admin_activation_code'])


@router.get('/', response_model=CustomPage[TenantAdminActivationCodeBase])
def get_tenant_admin_activation_codes_list_by_tenant_admin_id(
        tenant_admin_id: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    query_set = db_tenant_activation_code.get_tenant_admin_activation_codes_by_tenant_admin_id_active(db, tenant_admin_id)
    return paginate(query_set)


@router.post('/', response_model=TenantAdminActivationCodeBase)
def create_tenant_admin_activation_code(
        tenant_admin_id: int,
        db: Session = Depends(get_pg_db),
        sysadmin=Security(get_current_sysadmin)
):
    return db_tenant_activation_code.create_activation_code(db, tenant_admin_id)
