import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin
from database import db_integration
from database.database import get_pg_db
from models import Integrations
from models.identity import Attendance, Identity
from schemas.integration import IntegrationsBase, IntegrationsInDB, IntegrationsUpdate
from tasks import notify_integrator
from utils.pagination import CustomPage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])
description = """
```
attendance callback data:
{
    "message_id": str = d5beb032-5b65-46ae-bfb1-7c49fbcbde3d,
    "module_id": int = 1,
    "module_name": str = "FaceRecognition",
    "data": {
         "id": int = 1,
         "user_type": str = ["identity", "wanted", "visitor"],
         "user_group": int = 0,
         "pinfl": str = "12345678901234",
         "snapshot_url": str = "http://example.com/snapshot.jpg",
         "event_type": str = ["enter", "exit"],
         "capture_datetime": str = "2021-09-01 12:00:00",
         "capture_timestamp": int = 1630512000,
         "comp_score": float = 0.99,
         "device_lat": float = 41.102,
         "device_long": float = 60.231,
         "by_mobile": bool = False,
         "main_photo": str = "http://example.com/main_photo.jpg",
         "first_name": str = John,
         "last_name": str = Adam,
         "accusation": str = "JK 168-moddasi",
         "tenant_entity_id": int = 1,
         "address": str = "Yunusobod bozori",
         "camera_name": str = "Kirish kamerasi",
         "district": str = "Yunusobod t.",
         "description": str = "Mahalliy qidiruv",
         "concern_level": int = 1,
         "phone": str = "+998901234545",
         "room_id": int = 1,
         "room_name": str = "Asosiy Darvoza",
         "room_description": str = "Kirish joyi",
         "building_id": int = 1
    }
}

identity callback data:
{
    "is_success": bool = True [True, False],
    "message": str = "Identity added to camera successfully"
    "code": int = 200 [200, 400, 401, 404, 500],
    "type": str = "create" ["create", "update", "delete"],
    "id": 777,
    "identity_group": int = 1,
    "identity_type": str = ["staff", "kid", "relative"],
    "external_id": str = "12345",    
    "version": int = 1,
    "identity_first_name": "John Doe",
    "pinfl": str = "6846818168",
    "tenant_entity_id": int = 1,
    "device_lat": float = 41.102,
    "device_long": float = 60.231
}
```
"""


@router.post("/", response_model=IntegrationsInDB, description=description)
def create_integration(
    data: IntegrationsBase, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_integration.create_integration(db, tenant_admin.tenant_id, data)


@router.get("/", response_model=CustomPage[IntegrationsInDB])
def get_integrations(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_integration.get_integrations(db, tenant_admin.tenant_id, is_active)
    return paginate(query_set)


@router.get("/{pk}", response_model=IntegrationsInDB)
def get_integration(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_integration.get_integration(db, pk, tenant_admin.tenant_id, is_active)


@router.put("/{pk}", response_model=IntegrationsInDB)
def update_integration(
    pk: int, data: IntegrationsUpdate, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_integration.update_integration(db, pk, tenant_admin.tenant_id, data)


@router.delete("/{pk}", response_model=IntegrationsInDB)
def delete_integration(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    return db_integration.delete_integration(db, pk, tenant_admin.tenant_id)


@router.post("/send/attendance")
async def send_attendance(
    module_id: int,
    start_date: datetime,
    end_date: datetime,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    try:
        capture_time = datetime.now()  # timestamp behind 3 hours
    except Exception as e:
        capture_time = datetime.now()
        logger.error(f"Capture time error: {str(e)}")

    attendances = db.query(Attendance).filter(Attendance.attendance_datetime.between(start_date, end_date)).all()
    if not attendances:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No attendance found")

    integration = db.query(Integrations).filter_by(tenant_id=tenant_admin.tenant_id, module_id=module_id).first()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    identity_ids = {attendance.identity_id for attendance in attendances}
    identities = db.query(Identity).filter(Identity.id.in_(identity_ids)).all()
    identity_map = {identity.id: identity for identity in identities}
    for attendance in attendances:
        identity = identity_map.get(attendance.identity_id)
        if not identity:
            continue
        data = {
            "id": identity.id,
            "user_type": "identity",
            "user_group": identity.identity_group,
            "pinfl": identity.pinfl,
            "snapshot_url": attendance.snapshot_url,
            "event_type": attendance.attendance_type,
            "capture_datetime": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
            "capture_timestamp": int(capture_time.timestamp()),
            "comp_score": attendance.comp_score or 0.0,
        }
        notify_integrator.delay(
            module_id=1,
            module_name="Face Attendance",
            data=data,
            callback_url=integration.callback_url,
            auth_type=integration.auth_type,
            username=integration.username,
            password=integration.password,
            token=integration.token,
            token_type=integration.token_type,
        )
