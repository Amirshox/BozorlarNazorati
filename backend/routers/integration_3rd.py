import base64
import io
import json
import os
import uuid
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, List, Literal, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Security, status
from fastapi_pagination import Page
from fastapi_pagination import paginate as custom_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from minio import Minio
from minio.error import S3Error
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload, selectinload

from auth.oauth2 import get_current_third_party_token
from config import MTT_BASIC_PASSWORD, MTT_BASIC_USERNAME
from database import db_identity, db_smartcamera, db_tenant_entity, db_wanted, tenant
from database.database import get_mongo_db, get_pg_db
from database.minio_client import get_minio_client
from models import (
    Attendance,
    BazaarSmartCameraSnapshot,
    Building,
    Camera,
    District,
    Identity,
    IdentityPhoto,
    Roi,
    RoiPoint,
    Room,
    SmartCamera,
    SmartCameraSnapshot,
    TenantEntity,
)
from models.identity import Package
from schemas.attendance import AttendanceInDB, WantedAttendanceInDB
from schemas.identity import IdentityPhotoBase
from schemas.infrastructure import BazaarSmartCameraSnapshot as BazaarSmartCameraSnapshotSchema
from schemas.infrastructure import (
    SmartCameraInDB,
    SmartCameraSnapshotFullInDB,
    SmartCameraSnapshotInDB,
    SuccessIdResponse,
)
from schemas.kindergarten import SuccessResponse
from schemas.nvdsanalytics import BazaarRoi as BazaarRoiSchema
from schemas.nvdsanalytics import BazaarRoiInDB, CreateBazaarRoiInBulkRequest, RoiAnalyticsHistory, RoiAnalyticsResponse
from schemas.tenant import TenantInDBBase
from schemas.tenant_hierarchy_entity import TenantEntityInDB
from schemas.visitor import VisitorAttendanceInDB
from schemas.wanted import WantedBase, WantedInDB
from tasks import (
    add_wanted_to_smart_camera,
    send_attendance_leftovers_to_platon_service,
    send_attendance_to_platon_task,
    send_identity_photo_history,
    spoofing_check_task,
)
from utils.image_processing import get_image_from_query, get_main_error_text, make_minio_url_from_image
from utils.pagination import CustomPage

router = APIRouter(prefix="", tags=["integration"])

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")
SNAPSHOT_SCAMERA_BUCKET = os.getenv("SNAPSHOT_SCAMERA_BUCKET", "snapshot-scamera")
SNAPSHOT_BAZAAR_SCAMERA_BUCKET = os.getenv("SNAPSHOT_BAZAAR_SCAMERA_BUCKET", "bazaar-camera")
INFERENCED_SCAMERA_BUCKET = os.getenv("INFERENCED_SCAMERA_BUCKET", "inferenced-scamera")

WANTED_BUCKET = os.getenv("MINIO_BUCKET_WANTED", "wanted")
MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")

DETECTION_API = os.getenv("DETECTION_API", "http://10.3.7.131:8111/bazaar_inference")
# DETECTION_API = os.getenv("DETECTION_API", "http://0.0.0.0:8066/bazaar_inference")

BAZAAR_API = os.getenv("BAZAAR_API", "https://raqamli-bozor.uz/services/platon-core/api/v1/dev/1/roi/object-detection")
BAZAAR_API_USERNAME = os.getenv("BAZAAR_API_USERNAME", "ai")
BAZAAR_API_PASSWORD = os.getenv("BAZAAR_API_PASSWORD", "ydEB2WbJYhMLsTqwP8Rvnm")

BAZAAR_ID = "6e019d40-e226-e8b3-114b-ddce6f5c6bd0"

global_minio_client = get_minio_client()
if not global_minio_client.bucket_exists(WANTED_BUCKET):
    global_minio_client.make_bucket(WANTED_BUCKET)


def get_birth_date_from_pinfl(pinfl: str) -> str:
    if pinfl[0] in ["3", "4"]:
        return f"19{pinfl[5:7]}-{pinfl[3:5]}-{pinfl[1:3]}"
    elif pinfl[0] in ["5", "6"]:
        return f"20{pinfl[5:7]}-{pinfl[3:5]}-{pinfl[1:3]}"
    else:
        return "1111-11-11"


@router.get("/send/attendance/leftovers")
def send_attendance_leftovers_to_platon(
    tenant_id: int,
    mtt_id: int,
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
):
    unsent_count = send_attendance_leftovers_to_platon_service(db, tenant_id, mtt_id, date)
    return {"success": True, "unsent_count": unsent_count}


@router.get("/add/manual/attendance/to_spoofing", response_model=SuccessResponse)
def add_manual_attendance_to_spoofing(
    tenant_id: int,
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
):
    query = (
        db.query(Attendance)
        .join(TenantEntity, TenantEntity.id == Attendance.tenant_entity_id)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .filter(
            and_(
                Attendance.tenant_id == tenant_id,
                Attendance.attendance_datetime >= date,
                Attendance.attendance_datetime < date + timedelta(days=1),
                Attendance.snapshot_url.is_not(None),
                Attendance.mismatch_entity.is_(False),
                Attendance.version == 1,
                TenantEntity.is_active,
                Attendance.is_active,
            )
        )
    )
    if region_id:
        query = query.filter(TenantEntity.region_id == region_id)
    elif district_id:
        query = query.filter(TenantEntity.district_id == district_id)
    attendances = query.all()
    for attendance in attendances:
        if attendance.bucket_name == "identity-attendance":
            tenant_entity = (
                db.query(TenantEntity.id, TenantEntity.external_id, TenantEntity.spoofing_threshold)
                .filter_by(id=attendance.tenant_entity_id, is_active=True)
                .first()
            )
            package = db.query(Package).filter_by(uuid=attendance.package_uuid, is_active=True).first()
            package_verified = False
            if package:  # noqa
                if package.appLicensingVerdict == "LICENSED" and package.appRecognitionVerdict == "PLAY_RECOGNIZED":  # noqa
                    package_verified = True
            spoofing_task_data = {
                "bucket": attendance.bucket_name,
                "object_name": attendance.object_name,
                "lat": attendance.lat,
                "lon": attendance.lon,
                "app_version_name": attendance.app_version_name,
                "device_model": attendance.device_model,
                "device_ip": attendance.device_ip,
                "identity_id": attendance.identity.id,
                "kid_id": attendance.identity.external_id,
                "mtt_id": tenant_entity.external_id,
                "created_at": attendance.attendance_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                "attendance_spoofing_id": attendance.spoofing.id if attendance.spoofing else None,
                "spoofing_threshold": tenant_entity.spoofing_threshold,
                "package_verified": package_verified,
            }

            spoofing_check_task.delay(data=spoofing_task_data)
    return {"status": True}


@router.get("/daily_attendance", response_model=SuccessResponse)
def send_daily_attendance_to_platon(
    mtt_id: int,
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
    auth: str = Header(None, alias="X-Authorization"),
):
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    u, p = base64.b64decode(auth.split(" ")[1]).decode("utf-8").split(":")
    if u == MTT_BASIC_USERNAME and p == MTT_BASIC_PASSWORD:
        tenant_entity = (
            db.query(TenantEntity.id, TenantEntity.tenant_id)
            .filter_by(external_id=mtt_id, is_active=True)
            .filter(TenantEntity.tenant_id.in_([1, 18]))
            .first()
        )
        if not tenant_entity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
        send_attendance_to_platon_task.delay(
            tenant_entity.tenant_id, mtt_id, tenant_entity.id, 0, date.strftime("%Y-%m-%d")
        )
        send_attendance_to_platon_task.delay(
            tenant_entity.tenant_id, mtt_id, tenant_entity.id, 1, date.strftime("%Y-%m-%d")
        )
        return {"status": True}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


@router.get("/daily_attendance2", response_model=SuccessResponse)
def send_daily_attendance_to_platon2(
    region_id: int,
    tenant_id: int,
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
):
    if tenant_id in [1, 18]:
        tenant_entities = (
            db.query(TenantEntity.id, TenantEntity.external_id)
            .filter_by(region_id=region_id, tenant_id=tenant_id, is_active=True)
            .all()
        )
        for tenant_entity in tenant_entities:
            send_attendance_to_platon_task.delay(
                tenant_id, tenant_entity.external_id, tenant_entity.id, 0, date.strftime("%Y-%m-%d")
            )
            send_attendance_to_platon_task.delay(
                tenant_id, tenant_entity.external_id, tenant_entity.id, 1, date.strftime("%Y-%m-%d")
            )
        return {"status": True}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id must be 1 or 18")


class PlatonIdentityPhoto(BaseModel):
    id: int
    tenant_id: int
    identity_group: int
    photo_pk_list: Dict[str, int] | None = None


@router.post("/sync/identity/photos", response_model=SuccessResponse)
def sync_identity_photos(
    data: List[PlatonIdentityPhoto],
    db: Session = Depends(get_pg_db),
    auth: str = Header(None, alias="X-Authorization"),
):
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    u, p = base64.b64decode(auth.split(" ")[1]).decode("utf-8").split(":")
    if u == MTT_BASIC_USERNAME and p == MTT_BASIC_PASSWORD:
        for item in data:
            identity = (
                db.query(Identity)
                .filter_by(
                    tenant_id=item.tenant_id,
                    identity_group=item.identity_group,
                    external_id=str(item.id),
                    is_active=True,
                )
                .first()
            )
            if not identity:
                continue
            photos = db.query(IdentityPhoto).filter_by(identity_id=identity.id, is_active=True).all()
            if not photos:
                continue
            pk_list = item.photo_pk_list.values()
            for photo in photos:
                if photo.id not in pk_list:
                    photo_data = {
                        "identity_id": identity.id,
                        "id": int(str(identity.external_id)),
                        "tenant_id": identity.tenant_id,
                        "identity_group": identity.identity_group,
                        "photo_url": photo.url,
                        "bucket": identity.bucket_name,
                        "object_name": identity.object_name,
                        "photo_pk": photo.id,
                        "version": photo.version,
                        "photo_id": photo.photo_id,
                        "is_main": identity.photo == photo.url,
                        "created_at": photo.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    send_identity_photo_history.delay(photo_data)
        return {"status": True}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


@router.get("/identity/photo/history/{_id}", response_model=List[IdentityPhotoBase])
def get_identity_photo_history(
    _id: int,
    mtt_id: int,
    db: Session = Depends(get_pg_db),
    auth: str = Header(None, alias="X-Authorization"),
):
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    u, p = base64.b64decode(auth.split(" ")[1]).decode("utf-8").split(":")
    if u == MTT_BASIC_USERNAME and p == MTT_BASIC_PASSWORD:
        tenant_entity = (
            db.query(TenantEntity.id)
            .filter(
                and_(TenantEntity.tenant_id.in_([1, 18]), TenantEntity.external_id == mtt_id, TenantEntity.is_active)
            )
            .first()
        )
        if not tenant_entity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
        identity = (
            db.query(Identity)
            .filter(
                and_(
                    Identity.tenant_entity_id == tenant_entity.id, Identity.external_id == str(_id), Identity.is_active
                )
            )
            .first()
        )
        if not identity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
        return db_identity.get_identity_photo_history(db, identity.id)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


class MttCreateData(BaseModel):
    mtt_id: int
    name: str
    district_code: int
    location: str | None = None
    mahalla_code: int | None = None
    tin: str | None = None
    phone: str | None = None
    director_name: str | None = None
    director_pinfl: str | None = None
    director_image: str | None = None


@router.post("/tenant_entity/create", response_model=SuccessIdResponse)
def create_tenant_entity(
    tenant_id: int,
    data: MttCreateData,
    db: Session = Depends(get_pg_db),
    auth: str = Header(None, alias="X-Authorization"),
):
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    u, p = base64.b64decode(auth.split(" ")[1]).decode("utf-8").split(":")
    if u == MTT_BASIC_USERNAME and p == MTT_BASIC_PASSWORD:
        if data.location and "," not in data.location:
            data.location = None
        district = db.query(District).filter_by(external_id=data.district_code, is_active=True).first()
        if not district:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="District not found")
        parent_entity = (
            db.query(TenantEntity)
            .filter(
                and_(
                    TenantEntity.tenant_id == tenant_id,
                    TenantEntity.hierarchy_level == 2,
                    TenantEntity.is_active,
                    TenantEntity.region_id == district.region_id,
                )
            )
            .first()
        )
        if not parent_entity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent Entity not found")
        duplicate_entity = (
            db.query(TenantEntity)
            .filter_by(tenant_id=tenant_id, external_id=data.mtt_id, hierarchy_level=3, is_active=True)
            .first()
        )
        if duplicate_entity:
            return {"success": False, "message": "MTT already exists", "id": duplicate_entity.id}
        try:
            new_tenant_entity = TenantEntity(
                parent_id=parent_entity.id,
                name=data.name,
                district_id=district.id,
                country_id=1,
                region_id=district.region_id,
                tenant_id=tenant_id,
                hierarchy_level=3,
                external_id=data.mtt_id,
                lat=float(data.location.split(",")[0]) if data.location else None,
                lon=float(data.location.split(",")[1]) if data.location else None,
                mahalla_code=data.mahalla_code,
                tin=data.tin,
                phone=data.phone,
                director_name=data.director_name,
                director_pinfl=data.director_pinfl,
                director_image=data.director_image,
            )
            db.add(new_tenant_entity)
            db.commit()
            db.refresh(new_tenant_entity)
            return {"success": True, "message": "MTT created successfully", "id": new_tenant_entity.id}
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated") from None


@router.get("/tenant", response_model=CustomPage[TenantInDBBase])
def get_tenants(
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    query_set = tenant.get_3rd_tenants(db, tenant_ids)
    return paginate(query_set)


@router.get("/tenant/{pk}", response_model=TenantInDBBase)
def get_tenant(
    pk: int,
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    if pk not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant not found")
    return tenant.get_tenant(db, pk)


@router.get("/tenant_entity", response_model=CustomPage[TenantEntityInDB])
def get_tenant_entities(
    tenant_id: int,
    hierarchy_level: Optional[int] = Query(None, alias="hierarchy_level"),
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    if tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    query_set = db_tenant_entity.get_tenant_entities(db, tenant_id, hierarchy_level)
    return paginate(query_set)


@router.get("/tenant_entity/{pk}", response_model=TenantEntityInDB)
def get_tenant_entity(
    pk: int,
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    entity = db.query(TenantEntity).filter_by(id=pk, is_active=True).first()
    if not entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TenantEntity not found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    if entity.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    return entity


@router.get("/user/info/by_pinfl")
async def get_user_info_by_pinfl(
    pinfl: str, mongo_db=Depends(get_mongo_db), admin=Security(get_current_third_party_token)
):
    birth_date = get_birth_date_from_pinfl(pinfl)
    username, password = "online-bozor", "GYwMjrwJVpSx"
    url = f"https://wservice.uz/gcp/passport/info2?pinfl={pinfl}&birth_date={birth_date}"
    response = requests.get(url=url, auth=(username, password))
    try:
        response.raise_for_status()
        post = {
            "pinfl": pinfl,
            "third_id": admin.id,
            "data": response.json()["data"],
            "created_at": datetime.now(),
        }
        await mongo_db["pinfl-data"].insert_one(post)
        url = f"https://wservice.uz/gcp/v1/passport/photo?pinfl={pinfl}&birth_date={birth_date}"
        image_response = requests.get(url, auth=(username, password)).json()["data"]
        result = response.json()["data"]
        result["photo"] = image_response["photo"]
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/smartcamera/all", response_model=CustomPage[SmartCameraInDB])
def get_smartcameras(
    _id: int,
    get_by: Literal["tenant", "entity", "building", "room"] = "entity",
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    if get_by == "tenant":
        if _id not in tenant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    elif get_by == "entity":
        entity = db.query(TenantEntity).filter_by(id=_id, is_active=True).first()
        if not entity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="TenantEntity not found")
        if entity.tenant_id not in tenant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    elif get_by == "building":
        building = db.query(Building).filter_by(id=_id, is_active=True).first()
        if not building:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Building not found")
        if building.tenant_id not in tenant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    else:
        room = db.query(Room).filter_by(id=_id, is_active=True).first()
        if not room:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room not found")
        if room.tenant_id not in tenant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    query_set = db_smartcamera.super_get_smart_cameras(db, _id, get_by, is_active)
    return paginate(query_set)


@router.get("/smartcamera/rtmp_enable/{pk}")
async def rtmp_enable_or_disable_smart_camera_rtmp(
    pk: int,
    enable: Optional[bool] = Query(default=True, alias="enable"),
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    def get_response_text() -> str:
        return "Enabled" if enable else "Disabled"

    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    smart_camera = db_smartcamera.get_smart_camera_for_3(db, pk)
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
    if smart_camera.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
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
            return {
                "success": True,
                "message": f"Smart Camera Rtmp {get_response_text()}",
            }
        return HTTPException(status_code=400, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/smartcamera/snapshots", response_model=CustomPage[SmartCameraSnapshotInDB])
def get_smart_camera_snapshots(
    camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    query_set = db_smartcamera.get_snapshots_for_3(db, camera_id, tenant_ids, limit)
    return paginate(query_set)


@router.get("/smartcamera/snapshot/{pk}", response_model=SmartCameraSnapshotFullInDB)
def get_smart_camera_snapshot(pk: int, db: Session = Depends(get_pg_db), admin=Security(get_current_third_party_token)):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    snapshot = db.query(SmartCameraSnapshot).filter_by(id=pk, is_active=True).first()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
    if snapshot.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    result = SmartCameraSnapshotFullInDB(**snapshot.__dict__)
    smart_camera = db.query(SmartCamera).filter_by(id=snapshot.smart_camera_id, is_active=True).first()
    entity = db.query(TenantEntity).filter_by(id=smart_camera.tenant_entity_id, is_active=True).first()
    room = db.query(Room).filter_by(id=smart_camera.room_id, is_active=True).first()
    building = db.query(Building).filter_by(id=room.building_id, is_active=True).first()
    result.camera_name = smart_camera.name
    result.tenant_entity_name = entity.name
    result.building_name = building.name
    result.room_name = room.name
    result.room_description = room.description
    return result


@router.get("/smartcamera/visitor/attendances", response_model=CustomPage[VisitorAttendanceInDB])
def smart_camera_visitor_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    if smart_camera.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    query_set = db_smartcamera.get_user_attendances(db, "visitor", smart_camera_id, limit)
    return paginate(query_set)


@router.get("/smartcamera/identity/attendances", response_model=CustomPage[AttendanceInDB])
def smart_camera_identity_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    if smart_camera.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    query_set = db_smartcamera.get_user_attendances(db, "identity", smart_camera_id, limit)
    return paginate(query_set)


@router.get("/smartcamera/wanted/attendances", response_model=CustomPage[WantedAttendanceInDB])
def smart_camera_wanted_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    if smart_camera.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    query_set = db_smartcamera.get_user_attendances(db, "wanted", smart_camera_id, limit)
    return paginate(query_set)


@router.post("/wanted", response_model=WantedInDB)
def create_wanted(
    data: WantedBase,
    db: Session = Depends(get_pg_db),
    minio_client=Depends(get_minio_client),
    admin=Security(get_current_third_party_token),
):
    if not admin.tenants:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No tenants found")
    tenant_ids = [item.tenant_id for item in admin.tenants]
    if data.tenant_entity_id:
        entity = db.query(TenantEntity).filter_by(id=data.tenant_entity_id, is_active=True).first()
        if not entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TenantEntity not found")
        if entity.tenant_id not in tenant_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    main_image = get_image_from_query(data.photo)
    main_photo_url = make_minio_url_from_image(minio_client, main_image, WANTED_BUCKET, is_check_hd=False)
    data.photo = main_photo_url
    wanted = db_wanted.create_wanted(db, data)
    if data.tenant_entity_id:
        smart_cameras = db.query(SmartCamera).filter_by(tenant_entity_id=data.tenant_entity_id, is_active=True).all()
        for smart_camera in smart_cameras:
            add_wanted_to_smart_camera.delay(
                wanted.id,
                wanted.first_name,
                wanted.photo,
                wanted.concern_level,
                wanted.accusation,
                smart_camera.id,
                smart_camera.device_id,
                smart_camera.password,
                data.tenant_entity_id,
            )
    return wanted


@router.get("/stream_control/{pk}", tags=["bazaar"])
async def rtmp_enable_or_disable_smart_camera_stream(
    pk: int, enable: Optional[bool] = Query(default=True, alias="enable"), db: Session = Depends(get_pg_db)
):
    smart_camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
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
            return {"status": "Enabled" if enable else "Disabled", "stream_camera_url": smart_camera.stream_url}
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get(
    "/snapshot_history/{smart_camera_id}", tags=["bazaar"], response_model=List[BazaarSmartCameraSnapshotSchema]
)
def get_snapshot_history(smart_camera_id: int, db: Session = Depends(get_pg_db)):
    return (
        db.query(BazaarSmartCameraSnapshot).filter(BazaarSmartCameraSnapshot.smart_camera_id == smart_camera_id).all()
    )


@router.get("/roi_analytics", tags=["bazaar"], response_model=RoiAnalyticsResponse)
async def get_snapshot_roi_analytitcs(
    snapshot_id: int,
    minio_client: Minio = Depends(get_minio_client),
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    current_snapshot = db.query(BazaarSmartCameraSnapshot).filter(BazaarSmartCameraSnapshot.id == snapshot_id).first()

    if not current_snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BazaarSmartCameraSnapshot not found")

    current_smart_camera = db.query(SmartCamera).filter(SmartCamera.id == current_snapshot.smart_camera_id).first()

    if not current_smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SmartCamera not found")

    smart_camera_rois = db.query(Roi).filter(Roi.smart_camera_id == current_smart_camera.id, Roi.is_active).all()

    polygons = []

    for each_roi in smart_camera_rois:
        current_polygon_coordinates = []

        for each_roi_point in each_roi.points:
            current_polygon_coordinates.append([each_roi_point.x, each_roi_point.y])

        polygons.append({"id": each_roi.id, "coordinates": current_polygon_coordinates})

    object_filename = os.path.basename(current_snapshot.snapshot_url)

    try:
        response = minio_client.get_object(SNAPSHOT_BAZAAR_SCAMERA_BUCKET, object_filename)
    except S3Error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera snapshot cannot be found"
        ) from None

    image_bytes = BytesIO(response.read())

    inference_response = requests.post(
        DETECTION_API,
        json={"image": base64.b64encode(image_bytes.getvalue()).decode("utf-8"), "polygons": polygons},
    )

    detection_records = []

    if inference_response.status_code == 200:
        inference_result = inference_response.json()

        inferenced_detection_image_name = f"detection-{uuid.uuid4()}.jpg"

        image_data = base64.b64decode(inference_result["inferenced_image"])

        for each_polygon in inference_result["inferenced_polygons"]:
            current_roi = db.query(Roi).filter(Roi.id == each_polygon["id"]).first()

            detection_records.append(
                {
                    "roi_id": each_polygon["id"],
                    "spot_id": current_roi.spot_id if current_roi else None,
                    "shop_id": current_roi.shop_id if current_roi else None,
                    "is_covered": each_polygon["is_covered"],
                    "coverage_score": each_polygon["coverage_score"],
                    "detected_objects": each_polygon["detected_objects"],
                }
            )

        image_stream = BytesIO(image_data)

        if not minio_client.bucket_exists(INFERENCED_SCAMERA_BUCKET):
            minio_client.make_bucket(INFERENCED_SCAMERA_BUCKET)

        minio_client.put_object(
            INFERENCED_SCAMERA_BUCKET,
            inferenced_detection_image_name,
            data=image_stream,
            length=len(image_data),
            content_type="image/jpeg",
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, detail="Detection dependency service is not responding"
        )

    detection_record = {
        "@timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "inference_result": detection_records,
        "inference_image": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{INFERENCED_SCAMERA_BUCKET}/{inferenced_detection_image_name}",
        "inference_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "smart_camera_id": current_smart_camera.id,
    }

    await mongo_db["bazaar-inference"].insert_one(detection_record)

    del detection_record["_id"]

    requests.post(BAZAAR_API, json=detection_record, auth=(BAZAAR_API_USERNAME, BAZAAR_API_PASSWORD), timeout=10)

    return detection_record


@router.get("/roi_analytics_history", tags=["bazaar"], response_model=Page[RoiAnalyticsHistory])
async def get_roi_analytics_history(
    date: Optional[str] = None,
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    history_date = date if date else datetime.now().strftime("%Y-%m-%d")
    filtered_analytics_history = []

    analytics_history = (
        await mongo_db["bazaar-inference"]
        .find({"@timestamp": {"$gte": f"{history_date}T00:00:00", "$lte": f"{history_date}T23:59:59"}})
        .to_list(length=None)
    )

    for each_record in analytics_history:
        del each_record["_id"]
        each_record["inference_date"] = each_record["@timestamp"]
        del each_record["@timestamp"]
        filtered_analytics_history.append(each_record)

    return custom_paginate(analytics_history)


@router.get("/realtime_snapshot", tags=["bazaar"], response_model=BazaarSmartCameraSnapshotSchema)
def get_baazar_camera_snapshot(
    smart_camera_id: int, minio_client: Minio = Depends(get_minio_client), db: Session = Depends(get_pg_db)
):
    smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()

    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SmartCamera not found")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getFmtSnap"
    payload_dict = {"password": smart_camera.password, "fmt": 0}
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    if response.status_code != 200 or response.json()["code"] != 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=get_main_error_text(response))
    image_base64 = response.json()["image_base64"]
    image = io.BytesIO(base64.b64decode(image_base64))
    file_name = f"{uuid.uuid4()}.jpeg"
    if not minio_client.bucket_exists(SNAPSHOT_BAZAAR_SCAMERA_BUCKET):
        minio_client.make_bucket(SNAPSHOT_BAZAAR_SCAMERA_BUCKET)
    minio_client.put_object(
        SNAPSHOT_BAZAAR_SCAMERA_BUCKET,
        file_name,
        image,
        response.json()["image_length"],
    )
    photo_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{SNAPSHOT_BAZAAR_SCAMERA_BUCKET}/{file_name}"
    new_snapshot = BazaarSmartCameraSnapshot(
        smart_camera_id=smart_camera.id, snapshot_url=photo_url, tenant_id=smart_camera.tenant_id
    )
    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)
    return new_snapshot


@router.post("/bazaar_roi_single", response_model=BazaarRoiInDB, tags=["bazaar"])
def create_bazaar_roi(data: BazaarRoiSchema, db: Session = Depends(get_pg_db)):
    existing_roi = db.query(Roi).filter(Roi.shop_id == data.shop_id).first()

    if existing_roi is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Roi with given shop id ({data.shop_id}) already exists!"
        )

    camera_exists = db.query(Camera).filter(Camera.id == data.camera_id).first()

    if camera_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera with id({data.camera_id}) does not exist"
        )

    smart_camera_exists = db.query(SmartCamera).filter(Camera.id == data.smart_camera_id).first()

    if smart_camera_exists is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"SmartCamera with id({data.smart_camera_id}) does not exist"
        )

    bazaar_roi = Roi(
        name=data.name,
        description=data.description,
        color=data.color,
        smart_camera_id=data.smart_camera_id,
        camera_id=data.camera_id,
        shop_id=data.shop_id,
        spot_id=data.spot_id,
    )

    db.add(bazaar_roi)
    db.commit()
    db.refresh(bazaar_roi)

    for item in data.points:
        point = RoiPoint(x=item.x, y=item.y, order_number=item.order_number, roi_id=bazaar_roi.id)
        db.add(point)
        db.commit()
        db.refresh(point)

    return bazaar_roi


@router.post("/bazaar_roi_bulk", tags=["bazaar"])
def create_bazaar_roi_bulk(data: CreateBazaarRoiInBulkRequest, db: Session = Depends(get_pg_db)):
    smart_camera_exists = db.query(SmartCamera).filter(SmartCamera.id == data.smart_camera_id).first()

    if not smart_camera_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"SmartCamera with id({data.smart_camera_id}) does not exist"
        )

    created_rois = []

    for each_creating_roi in data.rois:
        if len(each_creating_roi.points) == 0:
            continue

        existing_roi = db.query(Roi).filter(Roi.shop_id == each_creating_roi.shop_id).first()

        if existing_roi is not None:
            all_roi_points = db.query(RoiPoint).filter(RoiPoint.roi_id == existing_roi.id).all()

            for each_roi in all_roi_points:
                db.delete(each_roi)

            db.delete(existing_roi)
            db.commit()

        bazaar_roi = Roi(
            name=each_creating_roi.name,
            color=each_creating_roi.color,
            smart_camera_id=data.smart_camera_id,
            shop_id=each_creating_roi.shop_id,
            spot_id=each_creating_roi.spot_id,
        )

        db.add(bazaar_roi)
        db.commit()
        db.refresh(bazaar_roi)

        for item in each_creating_roi.points:
            point = RoiPoint(x=item.x, y=item.y, order_number=item.order_number, roi_id=bazaar_roi.id)
            db.add(point)
            db.commit()
            db.refresh(point)

        created_rois.append(bazaar_roi)

    return created_rois


@router.get("/bazaar_rois/all", response_model=List[BazaarRoiInDB], tags=["bazaar"])
def get_bazaar_rois_all(db: Session = Depends(get_pg_db)):
    bazaar_rois = []

    bazaar_cameras = db.query(SmartCamera).filter(SmartCamera.tenant_id == 19, SmartCamera.is_active).all()

    for each_bazaar_camera in bazaar_cameras:
        current_rois = db.query(Roi).filter(Roi.smart_camera_id == each_bazaar_camera.id, Roi.is_active).all()

        bazaar_rois.extend(current_rois)

    return bazaar_rois


@router.get("/bazaar_rois/{smart_camera_id}", response_model=List[BazaarRoiInDB], tags=["bazaar"])
def get_bazaar_rois(smart_camera_id: int, db: Session = Depends(get_pg_db)):
    return db.query(Roi).filter(Roi.smart_camera_id == smart_camera_id, Roi.is_active).all()


@router.delete("/bazaar_roi/{roi_id}", response_model=BazaarRoiInDB, tags=["bazaar"])
def delete_bazaar_roi(roi_id: int, db: Session = Depends(get_pg_db)):
    deleting_roi = db.query(Roi).filter(Roi.id == roi_id, Roi.is_active).first()

    if not deleting_roi:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Roi with specified id is not found")

    all_roi_points = db.query(RoiPoint).filter(RoiPoint.roi_id == roi_id, RoiPoint.is_active).all()

    for each_point in all_roi_points:
        db.delete(each_point)

    db.commit()

    db.delete(deleting_roi)

    db.commit()

    return deleting_roi


@router.put("/bazaar_roi/update_payment_status", tags=["bazaar"])
def update_roi_payment_status(db: Session = Depends(get_pg_db)):
    url = f"https://sam-bozor.uz/services/platon-core/api/v1/ai/get/shop/statistics?emp_id={BAZAAR_ID}"

    response = requests.get(url, auth=(BAZAAR_API_USERNAME, BAZAAR_API_PASSWORD))

    if response.status_code == 200:
        payment_status_info = response.json().get("data")

        for each_shop in payment_status_info:
            shop_roi = db.query(Roi).filter(Roi.shop_id == each_shop["shop_id"], Roi.is_active).first()

            if not shop_roi:
                continue

            if each_shop["sum"] > 0:
                shop_roi.color = "#00FF00"
            else:
                shop_roi.color = "#FFFF00"

    db.commit()
