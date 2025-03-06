from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_sysadmin
from database import db_third_party
from database.database import get_pg_db
from models.third_party import AllowedEntity
from schemas.third_party import (
    AllowedEntityCreate,
    AllowedEntityResponse,
    ThirdPartyIntegrationCreate,
    ThirdPartyIntegrationInDB,
    ThirdPartyIntegrationUpdate,
)
from utils.pagination import CustomPage

router = APIRouter(prefix="/third_party", tags=["third_party"])


@router.post("/", response_model=ThirdPartyIntegrationInDB)
def create_third_party_integration(
    data: ThirdPartyIntegrationCreate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)
):
    return db_third_party.create_third_party(db, data)


@router.get("/", response_model=CustomPage[ThirdPartyIntegrationInDB])
def get_third_party_integrations(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    query_set = db_third_party.get_third_party_integrations(db, is_active)
    return paginate(query_set)


@router.get("/{pk}", response_model=ThirdPartyIntegrationInDB)
def get_third_party_integration(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return db_third_party.get_third_party(db, pk, is_active)


@router.put("/only_tenants/{pk}", response_model=ThirdPartyIntegrationInDB)
def update_third_party_integration_only_tenants(
    pk: int,
    tenant_ids: List[int],
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return db_third_party.update_3rd_party_only_tenants(db, pk, tenant_ids)


@router.put("/{pk}", response_model=ThirdPartyIntegrationInDB)
def update_third_party_integration(
    pk: int,
    data: ThirdPartyIntegrationUpdate,
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return db_third_party.update_third_party(db, pk, data)


@router.delete("/{pk}", response_model=ThirdPartyIntegrationInDB)
def delete_third_party_integration(pk: int, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db_third_party.delete_third_party(db, pk)


@router.post("/allowed_entity/", response_model=AllowedEntityResponse)
def create_allowed_entity(
    data: AllowedEntityCreate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)
):
    return db_third_party.create_allowed_entity(db, data)


@router.get("/allowed_entity/all", response_model=List[AllowedEntityResponse])
def get_allowed_entity_all(db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db.query(AllowedEntity).all()


@router.get("/allowed_entity/{pk}", response_model=AllowedEntityResponse)
def get_allowed_entity(pk: int, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    allowed_entity = db.query(AllowedEntity).filter_by(id=pk).first()
    if allowed_entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowed entity not found")
    return allowed_entity


@router.delete("/allowed_entity/{pk}")
def delete_allowed_entity(pk: int, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return db_third_party.delete_allowed_entity(db, pk)
