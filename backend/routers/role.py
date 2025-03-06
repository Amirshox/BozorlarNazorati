from typing import Optional

from fastapi import APIRouter, Depends, Query, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_sysadmin
from database import db_role
from database.database import get_pg_db
from schemas.role import RoleBase, RoleCreate, RoleUpdate
from schemas.shared import RoleBaseInDB, RoleInDBBase
from utils.pagination import CustomPage

router = APIRouter(prefix="/role", tags=["role"])


@router.get("/", response_model=CustomPage[RoleInDBBase])
def get_roles(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    query_set = db_role.get_roles(db, is_active)
    return paginate(query_set)


@router.get("/{pk}", response_model=RoleInDBBase)
def get_role(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return db_role.get_role(db, pk, is_active)


@router.post("/", response_model=RoleBaseInDB)
def create_role(role: RoleCreate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db_role.create_role(db, role)


@router.put("/{pk}", response_model=RoleBase)
def update_role(pk: int, role: RoleUpdate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db_role.update_role(db, pk, role)


@router.delete("/{pk}", response_model=RoleBase)
def delete_role(pk: int, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db_role.delete_role(db, pk)
