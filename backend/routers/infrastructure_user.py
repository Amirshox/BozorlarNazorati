import json
import os
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_tenant_entity_user
from database import db_building, db_camera, db_room, db_smartcamera
from database.database import get_pg_db
from models import SmartCamera
from schemas.infrastructure import BuildingInDB, CameraInDB, RoomInDB, SmartCameraInDB
from utils.image_processing import get_main_error_text
from utils.pagination import CustomPage

router = APIRouter(prefix="/infrastructure-customer", tags=["infrastructure"])

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")


@router.get("/building", response_model=List[BuildingInDB])
def get_buildings(
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    return db_building.get_buildings_by_user_permissions(db, user, is_active)


@router.get("/room", response_model=List[RoomInDB])
def get_rooms(
    building_id: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    return db_room.get_rooms_by_user_permissions(db, user, is_active, building_id)


@router.get("/camera", response_model=List[CameraInDB])
def get_cameras(
    room_id: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    return db_camera.get_cameras_by_user_permissions(db, user, room_id, is_active)


@router.get("/smartcamera", response_model=CustomPage[SmartCameraInDB])
def get_smart_cameras(
    room_id: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    query_set = db_smartcamera.get_smart_cameras_by_user_permissions(db, user, room_id, is_active)
    return paginate(query_set)


@router.get("/smartcamera/rtmp_enable/{pk}")
async def rtmp_enable_or_disable_smart_camera(
    pk: int,
    enable: Optional[bool] = Query(default=True, alias="enable"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    def get_response_text() -> str:
        return "Enabled" if enable else "Disabled"

    smart_camera = (
        db.query(SmartCamera).filter_by(id=pk, tenant_entity_id=user.tenant_entity_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found") from None
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setRtmpConf"
    payload_dict = {
        "password": smart_camera.password,
        "channel": 0,
        "RtmpEnable": 1 if enable else 0,
        "RtmpServerAddr": f"rtmp://92.63.207.75:1935/live/livestream_{smart_camera.device_id[-5:]}",
    }
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    try:
        response.raise_for_status()
        if response.json()["code"] == 0:
            smart_camera.stream_url = f"https://srs.realsoft.ai/live/livestream_{smart_camera.device_id[-5:]}.m3u8"
            db.commit()
            db.refresh(smart_camera)
            return {"success": True, "message": f"Smart Camera Rtmp {get_response_text()}"}
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
