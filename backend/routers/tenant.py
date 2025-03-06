from typing import Literal, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session
from starlette import status

from auth.oauth2 import get_current_sysadmin
from database import tenant
from database.database import get_pg_db
from models import GuessMessage, SmartCamera
from schemas.tenant import (
    GuessInDB,
    GuessMessageData,
    ScameraNoExistResponse,
    TenantCreate,
    TenantInDBBase,
    TenantUpdate,
)
from utils.pagination import CustomPage

router = APIRouter(prefix="/tenant", tags=["tenant"])


@router.post("/guess/message")
def save_guess_message(data: GuessMessageData, db: Session = Depends(get_pg_db)):
    new_guess = GuessMessage(**data.dict())
    db.add(new_guess)
    db.commit()
    db.refresh(new_guess)
    return {"success": True}


guess_description = """_status: Literal["NEW", "ARCHIVED", "SELECTED"]"""


@router.get("/guess/all", response_model=CustomPage[GuessInDB], description=guess_description)
def get_all_guesses(_status: Literal["NEW", "ARCHIVED", "SELECTED"] | None = "NEW", db: Session = Depends(get_pg_db)):
    query_set = db.query(GuessMessage).filter_by(status=_status, is_active=True)
    return paginate(query_set)


@router.put("/guess/{pk}", response_model=GuessInDB)
def update_guess(pk: int, _status: Literal["ARCHIVED", "SELECTED"], db: Session = Depends(get_pg_db)):
    guess = db.query(GuessMessage).filter_by(id=pk, is_active=True).first()
    if not guess:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Guess not found")
    guess.status = _status
    db.commit()
    db.refresh(guess)
    return guess


@router.get("/", response_model=CustomPage[TenantInDBBase])
def get_tenants(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    query_set = tenant.get_tenants(db, is_active)
    return paginate(query_set)


@router.post("/", response_model=TenantInDBBase)
def create_tenant(tenant_data: TenantCreate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return tenant.create_tenant(db, tenant_data)


@router.get("/{pk}", response_model=TenantInDBBase)
def get_tenant(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    sysadmin=Security(get_current_sysadmin),
):
    return tenant.get_tenant(db, pk, is_active)


@router.put("/{pk}", response_model=TenantInDBBase)
def update_tenant(
    pk: int, tenant_data: TenantUpdate, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)
):
    return tenant.update_tenant(db, pk, tenant_data)


@router.delete("/{pk}", response_model=TenantInDBBase)
def delete_tenant(pk: int, db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    return tenant.delete_tenant(db, pk)


@router.get("/smartcamera/no_exist/list")
def get_smartcamera_no_exist_list(db: Session = Depends(get_pg_db), sysadmin=Security(get_current_sysadmin)):
    url = "https://scamera.realsoft.ai/devices/getAllActiveDevices"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    all_active_devices: list = response.json()["devices"]
    if not all_active_devices:
        raise HTTPException(status_code=404, detail="No active devices found")
    db_scameras = db.query(SmartCamera).filter(SmartCamera.device_id.in_(all_active_devices)).all()
    if len(db_scameras) < len(all_active_devices):
        for scamera in db_scameras:
            if scamera.device_id in all_active_devices:
                all_active_devices.remove(scamera.device_id)
        return ScameraNoExistResponse(
            success=True, device_ids=all_active_devices, message=f"Amount: {len(all_active_devices)}"
        )
    elif len(db_scameras) == len(all_active_devices):
        return ScameraNoExistResponse(success=True, device_ids=None, message="No difference found")
    return ScameraNoExistResponse(success=True, device_ids=None, message=None)
