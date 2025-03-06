from sqlalchemy.orm import Session
from utils.pagination import CustomPage
from database.database import get_pg_db
from database import db_user_activation_code
from schemas.user import UserActivationCodeBase
from auth.oauth2 import get_current_tenant_admin
from fastapi import APIRouter, Depends, Security
from fastapi_pagination.ext.sqlalchemy import paginate

router = APIRouter(prefix='/user_activation_code', tags=['user_activation_code'])


@router.post('/', response_model=UserActivationCodeBase)
def create_user_activation_code(
        user_id: int,
        db: Session = Depends(get_pg_db),
        tenant_admin=Security(get_current_tenant_admin)
):
    return db_user_activation_code.create_user_activation_code(db, user_id)


@router.get('/{user_id}', response_model=CustomPage[UserActivationCodeBase])
def get_user_activation_codes(
        user_id: int,
        db: Session = Depends(get_pg_db),
        tenant_admin=Security(get_current_tenant_admin)
):
    query_set = db_user_activation_code.get_by_user_id_all(db, user_id)
    return paginate(query_set)
