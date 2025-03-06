import base64
import io
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
import sentry_sdk
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Security,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import and_, false, func
from sqlalchemy.orm import Session, aliased, joinedload, selectinload

from attestation import Attestation
from auth.oauth2 import get_entity_user_for_attendance_2, get_tenant_entity_user_2
from config import NODAVLAT_BOGCHA_BASE_URL
from database import db_identity
from database.database import get_pg_db
from database.db_attestation import get_attestation, get_attestation2
from database.db_identity import delete_extra_attendances, get_package_by_uuid
from database.db_smartcamera import create_task_to_scamera
from database.hash import verify_api_signature
from database.minio_client import get_minio_client, get_minio_ssd_client
from models import (
    AllowedEntity,
    Attendance,
    AttendanceAntiSpoofing,
    ErrorSmartCamera,
    ExtraAttendance,
    Identity,
    Notification,
    SimilarityAttendancePhotoInArea,
    SimilarityAttendancePhotoInEntity,
    SimilarityMainPhotoInArea,
    SimilarityMainPhotoInEntity,
    SmartCamera,
    TenantEntity,
    UpdateIdentity,
    UserFCMToken,
)
from models.identity import AppDetail, AttendanceReport, CustomLocation, IdentityRelative, Package, RelativeAttendance
from schemas.attendance import (
    AttendanceCreate,
    AttendanceDetails,
    AttendanceInDB,
    AttendanceReportCreate,
    AttendanceReportInDB,
    AttendanceReportMini,
    AttendanceReportV2InDB,
    ExternalUserTokenResponse,
)
from schemas.identity import (
    AppDetailsData,
    CustomLocationInDB,
    IdentityBase,
    IdentityBaseForRelative,
    IdentityCreate,
    IdentityInDB,
    IdentityPhotoBase,
    IdentitySelect,
    IdentitySelectWithPhotos,
    IdentityUpdate,
    NotificationInDB,
    PackageBase,
    PackageResponse,
    ParentAttendanceScheme,
    RelativeBase,
    SimpleResponse,
)
from schemas.kindergarten import ExtraAttendanceCreate
from tasks import send_express_attendance_batch, spoofing_check_task
from utils import kindergarten
from utils.generator import extract_attestation, extract_jwt_token
from utils.image_processing import get_image_from_query, is_image_url, make_minio_url_from_image
from utils.kindergarten import BASIC_AUTH
from utils.pagination import CustomPage
from utils.redis_cache import get_from_redis, get_redis_connection, set_to_redis

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/identity", tags=["identity"])
mobile_router = APIRouter(prefix="/identity", tags=["Mobile"])

IDENTITY_BUCKET = os.getenv("MINIO_BUCKET_IDENTITY", "identity")
BUCKET_IDENTITY_ATTENDANCE = os.getenv("BUCKET_IDENTITY_ATTENDANCE", "identity-attendance")

MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")
MINIO_HOST3 = os.getenv("MINIO_HOST3")
CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")

global_minio_client = get_minio_client()
global_minio_ssd_client = get_minio_ssd_client()
if not global_minio_client.bucket_exists(IDENTITY_BUCKET):
    global_minio_client.make_bucket(IDENTITY_BUCKET)
if not global_minio_client.bucket_exists(BUCKET_IDENTITY_ATTENDANCE):
    global_minio_client.make_bucket(BUCKET_IDENTITY_ATTENDANCE)
if not global_minio_ssd_client.bucket_exists(BUCKET_IDENTITY_ATTENDANCE):
    global_minio_ssd_client.make_bucket(BUCKET_IDENTITY_ATTENDANCE)
if not global_minio_ssd_client.bucket_exists(IDENTITY_BUCKET):
    global_minio_ssd_client.make_bucket(IDENTITY_BUCKET)

rooms: Dict[int, Dict[str, Any]] = {}
entity_users: Dict[int, WebSocket] = {}


class OfferResponse(BaseModel):
    url: str


class CustomMttLocationData(BaseModel):
    lat: float
    lon: float
    description: str | None = None


@mobile_router.get("/offer", response_model=OfferResponse)
def get_offer():
    return {"url": "https://s33.realsoft.ai/offer/v1/eb05a8a0-165e-45cf-b74b-56360749ede2/offer.pdf"}


@mobile_router.post("/mtt/custom/location", response_model=SimpleResponse)
def save_custom_location(
    data: CustomMttLocationData,
    app_version_code: int = Header(None, alias="App-Version-Code"),
    app_version_name: str = Header(None, alias="App-Version-Name"),
    device_id: str = Header(None, alias="Device-Id"),
    device_name: str = Header(None, alias="Device-Name"),
    device_model: str = Header(None, alias="Device-Model"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    new_location = CustomLocation(
        user_id=user.id,
        lat=data.lat,
        lon=data.lon,
        description=data.description,
        app_version_code=app_version_code,
        app_version_name=app_version_name,
        device_id=device_id,
        device_name=device_name,
        device_model=device_model,
        tenant_entity_id=user.tenant_entity_id,
    )
    db.add(new_location)
    db.commit()
    return {"success": True, "message": None}


@mobile_router.get("/mtt/custom/location", response_model=List[CustomLocationInDB])
def get_mtt_custom_locations(db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user_2)):
    return (
        db.query(CustomLocation)
        .filter_by(user_id=user.id, is_active=True)
        .order_by(CustomLocation.created_at.desc())
        .all()
    )


@mobile_router.post("/app/history", response_model=SimpleResponse)
def save_app_history(
    data: List[AppDetailsData],
    device_id: str = Header(None, alias="Device-Id"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    if not device_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device-Id is required.")
    try:
        app_history_objects = [AppDetail(**item.dict(), user_id=user.id, device_id=device_id) for item in data]
        db.add_all(app_history_objects)
        db.commit()
        return {"success": True, "message": f"Inserted {len(app_history_objects)} items."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@mobile_router.put("/fcmtoken/register", response_model=SimpleResponse)
def set_fcm_token(
    token: str,
    device_id: str = Header(None, alias="Device-Id"),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    app_version_name: str = Header(None, alias="App-Version-Name"),
    device_name: str = Header(None, alias="Device-Name"),
    device_model: str = Header(None, alias="Device-Model"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    fcm_token = db.query(UserFCMToken).filter_by(user_id=user.id, device_id=device_id, is_active=True).first()
    if fcm_token:
        fcm_token.token = token
        fcm_token.app_version_code = app_version_code
        fcm_token.app_version_name = app_version_name
        fcm_token.device_name = device_name
        fcm_token.device_model = device_model
        db.commit()
        db.refresh(fcm_token)
    else:
        new_fcm_token = UserFCMToken(
            user_id=user.id,
            device_id=device_id,
            token=token,
            app_version_code=app_version_code,
            app_version_name=app_version_name,
            device_name=device_name,
            device_model=device_model,
        )
        db.add(new_fcm_token)
        db.commit()
        db.refresh(new_fcm_token)
    return {"success": True, "message": None}


@mobile_router.put("/fcmtoken/deactivate", response_model=SimpleResponse)
def delete_fcm_token(
    device_id: str = Header(None, alias="Device-Id"),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    app_version_name: str = Header(None, alias="App-Version-Name"),
    device_name: str = Header(None, alias="Device-Name"),
    device_model: str = Header(None, alias="Device-Model"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    fcm_token = db.query(UserFCMToken).filter_by(user_id=user.id, device_id=device_id, is_active=True).first()
    if fcm_token:
        fcm_token.is_active = False
        fcm_token.app_version_code = app_version_code
        fcm_token.app_version_name = app_version_name
        fcm_token.device_name = device_name
        fcm_token.device_model = device_model
        db.commit()
        db.refresh(fcm_token)
    return {"success": True, "message": None}


@mobile_router.get("/notification/all", response_model=CustomPage[NotificationInDB])
def get_all_notifications(db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user_2)):
    query_set = (
        db.query(Notification)
        .filter_by(receiver_id=user.id, receiver_type="user", is_active=True)
        .order_by(Notification.created_at.desc())
    )
    return paginate(query_set)


@mobile_router.post("/package", response_model=PackageResponse)
def create_attendance_package(
    data: PackageBase, db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user_2)
):
    new_package = Package(**data.dict())
    new_package.tenant_entity_id = user.tenant_entity_id
    new_package.tenant_id = user.tenant_id

    attestation = Attestation(data.integrity_token, "uz.realsoft.ai.onesystemmoblie")

    attestation_data = attestation.get_data() or {}
    if attestation_data:
        att_data = extract_attestation(attestation_data)
        if att_data:
            new_package.appRecognitionVerdict = att_data.app_recognition_verdict
            new_package.appLicensingVerdict = att_data.app_licensing_verdict
            new_package.deviceActivityLevel = att_data.device_activity_level
            new_package.deviceRecognitionVerdict = att_data.device_recognition_verdict
            new_package.playProtectVerdict = att_data.play_protect_verdict
            new_package.request_nonce = att_data.request_nonce
            new_package.request_hash = att_data.request_hash
            new_package.request_timestamp_millis = (
                int(att_data.request_timestamp_millis) if att_data.request_timestamp_millis else None
            )
            new_package.appsDetected = att_data.apps_detected

    db.add(new_package)
    db.commit()
    db.refresh(new_package)
    return new_package


@mobile_router.put("/attendance/invalid_recognition/{attendance_id}", response_model=AttendanceInDB)
def set_invalid_attendance(
    attendance_id: int,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    attendance = (
        db.query(Attendance).filter_by(id=attendance_id, tenant_entity_id=user.tenant_entity_id, is_active=True).first()
    )
    if not attendance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance not found")
    identity = (
        db.query(Identity.id, Identity.external_id, Identity.identity_group)
        .filter_by(id=attendance.identity_id)
        .first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id)
        .filter_by(id=attendance.tenant_entity_id, is_active=True)
        .first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    attendance.is_valid_recognition = False
    attendance.version += 1
    db.commit()
    db.refresh(attendance)
    r = requests.post(
        url=NODAVLAT_BOGCHA_BASE_URL + "visit/cancel",
        headers=BASIC_AUTH,
        json={
            "tenant_id": attendance.tenant_id,
            "mtt_id": tenant_entity.external_id,
            "identity_id": int(identity.external_id),
            "identity_group": identity.identity_group,
            "visit_date": attendance.attendance_datetime.strftime("%Y-%m-%d"),
            "username": user.email,
        },
        timeout=10,
    )
    try:
        r.raise_for_status()
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manba ma'lumotida xatolik!") from e
    return attendance


@mobile_router.get("/external_user_token", response_model=ExternalUserTokenResponse)
def get_external_user_token(agent: str = Header(None, alias="User-Agent"), user=Security(get_tenant_entity_user_2)):
    if not user.pwd:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iltimos, tizimga qayta kirib chiqing!")
    mtt_user_response = kindergarten.get_auth_user(user.email, user.pwd, agent)
    if mtt_user_response["success"]:
        return {"success": True, "token": mtt_user_response["token"]}
    if str(mtt_user_response["code"]).startswith("2"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manba ma'lumotida xatolik!")
    if str(mtt_user_response["code"]).startswith("4"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ushbu amaliyot uchun ruxsat berilmagan!")
    if str(mtt_user_response["code"]).startswith("5"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manba bilan bog'lanishda xatolik!")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid credentials")


@mobile_router.post("/attendance_report", response_model=AttendanceReportMini)
def send_attendance_report(
    request: Request,
    data: AttendanceReportCreate,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    headers = request.headers
    attendance = db.query(Attendance).filter_by(id=data.attendance_id, is_active=True).first()
    if not attendance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance not found")
    old_report = (
        db.query(AttendanceReport)
        .filter_by(attendance_id=data.attendance_id, status="IN_PROGRESS", is_active=True)
        .first()
    )
    if old_report:
        sent_date = old_report.created_at.strftime("%Y-%m-%d %H:%M:%S")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ushbu davomat bo'yicha {sent_date} da so'rov berilgan, iltimos javobini kuting!",
        )
    if attendance.bucket_name != "compromised-attendance":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ushbu davomat shubhali emas!")

    app_version_code = headers.get("App-Version-Code", None)
    app_version_name = headers.get("App-Version-Name", None)
    device_id = headers.get("Device-Id", None)
    device_ip = headers.get("Device-IP", None)
    device_name = headers.get("Device-Name", None)
    device_model = headers.get("Device-Model", None)
    new_report = AttendanceReport(
        user_id=user.id,
        attendance_id=data.attendance_id,
        tenant_entity_id=attendance.tenant_entity_id,
        description=data.description,
        app_version_code=int(app_version_code) if app_version_code else None,
        app_version_name=app_version_name,
        device_id=device_id,
        device_ip=device_ip,
        device_name=device_name,
        device_model=device_model,
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    start_time = datetime.now()
    r = requests.post(
        url=NODAVLAT_BOGCHA_BASE_URL + "visits/kids/moderation",
        headers=BASIC_AUTH,
        json={
            "id": new_report.id,
            "kid_id": int(attendance.identity.external_id),
            "mtt_id": user.tenant_entity.external_id,
            "visit_date": attendance.attendance_datetime.strftime("%Y-%m-%d"),
            "bucket": attendance.bucket_name,
            "object_name": attendance.object_name,
            "description": data.description,
            "attendance_id": data.attendance_id,
            "tenant_id": attendance.tenant_id,
            "identity_group": attendance.identity.identity_group,
        },
        timeout=5,
    )
    end_time = datetime.now()
    print(f"spent_time(send_attendance_report): {(end_time - start_time).total_seconds():.2f} s")
    if r.status_code != 200:
        db.delete(new_report)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik! Iltimos, qayta urinib ko'ring!"
        )
    return new_report


@mobile_router.get("/attendance_reports", response_model=List[AttendanceReportInDB])
def get_attendance_reports(
    start_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    end_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    return (
        db.query(AttendanceReport)
        .join(Attendance, Attendance.id == AttendanceReport.attendance_id)
        .filter(
            Attendance.tenant_entity_id == user.tenant_entity_id,
            AttendanceReport.created_at >= start_date,
            AttendanceReport.created_at < end_date + timedelta(days=1),
            Attendance.is_active,
        )
        .all()
    )


@mobile_router.get("/review_reports", response_model=List[AttendanceReportV2InDB])
def get_attendance_review_reports(
    start_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    end_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    data = (
        db.query(AttendanceReport)
        .join(Attendance, Attendance.id == AttendanceReport.attendance_id)
        .filter(
            Attendance.tenant_entity_id == user.tenant_entity_id,
            AttendanceReport.created_at >= start_date,
            AttendanceReport.created_at < end_date + timedelta(days=1),
            Attendance.is_active,
        )
        .all()
    )
    result = [AttendanceReportV2InDB.model_validate(report) for report in data]
    return result


@mobile_router.delete("/wrong_attendance/{attendance_id}", response_model=SimpleResponse)
def delete_wrong_attendance(
    attendance_id: int, db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user_2)
):
    attendance = (
        db.query(Attendance).filter_by(id=attendance_id, tenant_entity_id=user.tenant_entity_id, is_active=True).first()
    )
    if not attendance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance not found")
    attendance.is_active = False
    attendance.version += 1
    db.commit()
    return {"success": True, "message": None}


@mobile_router.post("/set/recognisable_photo", response_model=IdentityInDB)
def set_recognisable_photo(
    identity_id: int,
    photo_url: str,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    identity = (
        db.query(Identity).filter_by(id=identity_id, tenant_entity_id=user.tenant_entity_id, is_active=True).first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    identity.recognisable_photo = photo_url
    identity.version += 1
    db.commit()
    db.refresh(identity)
    return identity


@router.get("/photo/history/all", response_model=List[IdentityPhotoBase])
def get_identity_photo_history(
    identity_id: int, db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user_2)
):
    return db_identity.get_identity_photo_history(db, identity_id)


@router.post("/", response_model=IdentityInDB)
async def create_identity(
    data: IdentityBase,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    minio_ssd_client=Depends(get_minio_ssd_client),
):
    recieved_photo_url = None
    if data.photo:
        recieved_photo_url = data.photo if is_image_url(data.photo) else None
        main_image = get_image_from_query(data.photo)
        main_photo_url = make_minio_url_from_image(
            minio_ssd_client, main_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.photo = main_photo_url
    if data.left_side_photo:
        left_image = get_image_from_query(data.left_side_photo)
        left_photo_url = make_minio_url_from_image(
            minio_ssd_client, left_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.left_side_photo = left_photo_url
    if data.right_side_photo:
        right_image = get_image_from_query(data.right_side_photo)
        right_photo_url = make_minio_url_from_image(
            minio_ssd_client, right_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.right_side_photo = right_photo_url
    if data.top_side_photo:
        top_image = get_image_from_query(data.top_side_photo)
        top_photo_url = make_minio_url_from_image(
            minio_ssd_client, top_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.top_side_photo = top_photo_url
    if data.cropped_image:
        cropped_image = get_image_from_query(data.cropped_image)
        cropped_photo_url = make_minio_url_from_image(
            minio_ssd_client,
            cropped_image,
            IDENTITY_BUCKET,
            data.pinfl,
            is_check_hd=False,
            is_check_size=False,
            minio_host=MINIO_HOST3,
        )
        data.cropped_image = cropped_photo_url
    if data.cropped_image512:
        cropped_image512 = get_image_from_query(data.cropped_image512)
        cropped_photo512_url = make_minio_url_from_image(
            minio_ssd_client,
            cropped_image512,
            IDENTITY_BUCKET,
            data.pinfl,
            is_check_hd=False,
            is_check_size=False,
            minio_host=MINIO_HOST3,
        )
        data.cropped_image512 = cropped_photo512_url
    if data.i_cropped_image512:
        i_cropped_image512 = get_image_from_query(data.i_cropped_image512)
        i_cropped_photo512_url = make_minio_url_from_image(
            minio_ssd_client,
            i_cropped_image512,
            IDENTITY_BUCKET,
            data.pinfl,
            is_check_hd=False,
            is_check_size=False,
            minio_host=MINIO_HOST3,
        )
        data.i_cropped_image512 = i_cropped_photo512_url
    new_data = IdentityCreate(
        first_name=data.first_name,
        last_name=data.last_name,
        photo=data.photo,
        email=data.email,
        phone=data.phone,
        pinfl=data.pinfl,
        identity_group=data.identity_group,
        identity_type=data.identity_type,
        left_side_photo=data.left_side_photo,
        right_side_photo=data.right_side_photo,
        top_side_photo=data.top_side_photo,
        embedding=data.embedding,
        cropped_image=data.cropped_image,
        embedding512=data.embedding512,
        cropped_image512=data.cropped_image512,
        i_embedding512=data.i_embedding512,
        i_cropped_image512=data.i_cropped_image512,
        external_id=data.external_id,
        group_id=data.group_id,
        group_name=data.group_name,
        tenant_entity_id=user.tenant_entity_id,
    )
    identity = db_identity.create_identity(db, user.tenant_id, new_data, recieved_photo_url, user.email)
    smart_camera_ids = (
        db.query(SmartCamera.id).filter_by(tenant_entity_id=identity.tenant_entity_id, is_active=True).all()
    )
    if identity.photo:
        for smart_camera in smart_camera_ids:
            create_task_to_scamera(db, "add", smart_camera.id, identity.id, "identity")
    return identity


@router.get("/", response_model=CustomPage[IdentityInDB])
def get_identities(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    return paginate(db_identity.get_identities_by_entity_id(db, user.tenant_entity_id, is_active))


@mobile_router.get("/all", response_model=List[IdentitySelect], description="Get all without pagination")
def get_identities_without_pagination(
    use_cache: bool = False,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    redis_client=Depends(get_redis_connection),
):
    cache_key = f"identity:{user.tenant_entity_id}:no_pagination"
    if use_cache:
        cached_data = get_from_redis(redis_client, cache_key)
        if cached_data:
            return cached_data

    kids = (
        db.query(Identity)
        .options(selectinload(Identity.extra_attendances))
        .filter_by(tenant_entity_id=user.tenant_entity_id, deleted=False, identity_group=0)
        .all()
    )
    # kids = kids_query.filter_by(is_active=True).all() if user.tenant_id == 1 else kids_query.all()

    staffs = (
        db.query(Identity)
        .options(selectinload(Identity.photos), selectinload(Identity.extra_attendances))
        .filter_by(tenant_entity_id=user.tenant_entity_id, deleted=False, identity_group=1)
        .all()
    )
    # staffs = staffs_query.filter_by(is_active=True).all() if user.tenant_id == 1 else staffs_query.all()

    kids_result = [IdentitySelect.model_validate(identity) for identity in kids]
    staffs_result = [IdentitySelect.model_validate(identity) for identity in staffs]

    for staff_identity, staff_model in zip(staffs, staffs_result):
        if staff_identity.photos:
            latest_photo = max(staff_identity.photos, key=lambda p: p.created_at, default=None)
            if latest_photo:
                if latest_photo.passport_verification_result is True:
                    verification_result = 1
                elif latest_photo.passport_verification_result is False:
                    verification_result = 2
                else:
                    verification_result = 0

                staff_model.passport_verification_result = verification_result

    result = staffs_result + kids_result

    if use_cache:
        set_to_redis(redis_client, cache_key, result)

    return result


@mobile_router.get("/all_with_photos", response_model=List[IdentitySelectWithPhotos])
def get_identities_without_pagination_with_photos(
    use_cache: bool = False,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    redis_client=Depends(get_redis_connection),
):
    cache_key = f"identity:{user.tenant_entity_id}:no_pagination"
    if use_cache:
        cached_data = get_from_redis(redis_client, cache_key)
        if cached_data:
            return cached_data

    kids_query = (
        db.query(Identity)
        .options(selectinload(Identity.extra_attendances), selectinload(Identity.photos))
        .filter_by(tenant_entity_id=user.tenant_entity_id, deleted=False, identity_group=0)
    )
    kids = kids_query.filter_by(is_active=True).all() if user.tenant_id == 1 else kids_query.all()
    for kid in kids:
        kid.photos = sorted(kid.photos, key=lambda p: p.created_at, reverse=True)[:5]

    staffs_query = (
        db.query(Identity)
        .options(selectinload(Identity.extra_attendances), selectinload(Identity.photos))
        .filter_by(tenant_entity_id=user.tenant_entity_id, deleted=False, identity_group=1)
    )
    staffs = staffs_query.filter_by(is_active=True).all() if user.tenant_id == 1 else staffs_query.all()
    for staff in staffs:
        staff.photos = sorted(staff.photos, key=lambda p: p.created_at, reverse=True)[:5]

    kids_result = [IdentitySelectWithPhotos.model_validate(identity) for identity in kids]
    staffs_result = [IdentitySelectWithPhotos.model_validate(identity) for identity in staffs]

    for staff_identity, staff_model in zip(staffs, staffs_result):
        if staff_identity.photos:
            latest_photo = max(staff_identity.photos, key=lambda p: p.created_at, default=None)
            if latest_photo:
                if latest_photo.passport_verification_result is True:
                    verification_result = 1
                elif latest_photo.passport_verification_result is False:
                    verification_result = 2
                else:
                    verification_result = 0

                staff_model.passport_verification_result = verification_result

    result = staffs_result + kids_result

    if use_cache:
        set_to_redis(redis_client, cache_key, result)

    return result


@router.get("/by_pinfl", response_model=IdentityInDB)
def get_identity_by_pinfl(
    pinfl: str,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    identity = db_identity.get_identity_by_pinfl(db, user.tenant_id, pinfl, is_active)
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Identity not found with pinfl {pinfl}"
        ) from None
    return identity


@router.put("/{pk}", response_model=IdentityInDB)
async def update_identity(
    pk: int,
    data: IdentityUpdate,
    x_signature: Optional[str] = Header(None),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    app_version_name: str = Header(None, alias="App-Version-Name"),
    device_id: str = Header(None, alias="Device-Id"),
    device_ip: str = Header(None),
    device_name: str = Header(None, alias="Device-Name"),
    device_model: str = Header(None, alias="Device-Model"),
    verified_by: Optional[int] = None,  # 1 - face, 2 - fingerprint, 3 - pin code
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    minio_ssd_client=Depends(get_minio_ssd_client),
):
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.signature_key)
        .filter_by(id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if x_signature:
        try:
            payload = json.dumps(data.__dict__)
            s_key = base64.b64encode(tenant_entity.signature_key.encode("utf-8")).decode("utf-8")
            is_valid = verify_api_signature(payload, x_signature, s_key)
            if not is_valid:
                pass
                # logger.info("Invalid signature.")
            else:
                logger.info("Signature successfully verified.")
        except UnicodeDecodeError:
            logger.warning("Payload is not valid UTF-8.")
    identity = db.query(Identity).filter_by(id=pk, tenant_entity_id=user.tenant_entity_id).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found") from None
    if identity.recieved_photo_url != data.photo:
        main_image = get_image_from_query(data.photo)
        main_photo_url = make_minio_url_from_image(
            minio_ssd_client, main_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.photo = main_photo_url
        identity.recieved_photo_url = data.photo if is_image_url(data.photo) else None
        db.commit()
        db.refresh(identity)
    if data.left_side_photo and identity.left_side_photo != data.left_side_photo:
        left_image = get_image_from_query(data.left_side_photo)
        left_photo_url = make_minio_url_from_image(
            minio_ssd_client, left_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.left_side_photo = left_photo_url
    if data.right_side_photo and identity.right_side_photo != data.right_side_photo:
        right_image = get_image_from_query(data.right_side_photo)
        right_photo_url = make_minio_url_from_image(
            minio_ssd_client, right_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.right_side_photo = right_photo_url
    if data.top_side_photo and identity.top_side_photo != data.top_side_photo:
        top_image = get_image_from_query(data.top_side_photo)
        top_photo_url = make_minio_url_from_image(
            minio_ssd_client, top_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.top_side_photo = top_photo_url
    if data.cropped_image:
        cropped_image = get_image_from_query(data.cropped_image)
        cropped_photo_url = make_minio_url_from_image(
            minio_ssd_client,
            cropped_image,
            IDENTITY_BUCKET,
            data.pinfl,
            is_check_hd=False,
            is_check_size=False,
            minio_host=MINIO_HOST3,
        )
        data.cropped_image = cropped_photo_url
    if data.cropped_image512:
        cropped_image512 = get_image_from_query(data.cropped_image512)
        cropped_photo512_url = make_minio_url_from_image(
            minio_ssd_client,
            cropped_image512,
            IDENTITY_BUCKET,
            data.pinfl,
            is_check_hd=False,
            is_check_size=False,
            minio_host=MINIO_HOST3,
        )
        data.cropped_image512 = cropped_photo512_url
    if data.i_cropped_image512:
        i_cropped_image512 = get_image_from_query(data.i_cropped_image512)
        i_cropped_photo512_url = make_minio_url_from_image(
            minio_ssd_client,
            i_cropped_image512,
            IDENTITY_BUCKET,
            data.pinfl,
            is_check_hd=False,
            is_check_size=False,
            minio_host=MINIO_HOST3,
        )
        data.i_cropped_image512 = i_cropped_photo512_url

    db.query(ErrorSmartCamera).filter_by(identity_id=pk, is_active=True).delete()

    identity = db_identity.update_identity(db, user.tenant_id, pk, data, user.email)

    update_item = UpdateIdentity(
        user_id=user.id,
        identity_id=identity.id,
        version=identity.version,
        app_version_code=app_version_code,
        app_version_name=app_version_name,
        device_id=device_id,
        device_ip=device_ip,
        device_name=device_name,
        device_model=device_model,
        verified_by=verified_by,
        tenant_entity_id=user.tenant_entity_id,
    )
    db.add(update_item)
    db.commit()

    smart_camera_ids = (
        db.query(SmartCamera.id).filter_by(tenant_entity_id=identity.tenant_entity_id, is_active=True).all()
    )
    if identity.photo:
        for smart_camera in smart_camera_ids:
            create_task_to_scamera(db, "update", smart_camera.id, identity.id, "identity")
    return identity


@mobile_router.post("/attendance", response_model=AttendanceInDB)
async def create_identity_attendance(
    request: Request,
    attendance_data: AttendanceCreate,
    x_signature: str = Header(None, alias="X-Signature"),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    app_version_name: str = Header(None, alias="App-Version-Name"),
    device_id: str = Header(None, alias="Device-Id"),
    device_ip: str = Header(None),
    device_name: str = Header(None, alias="Device-Name"),
    device_model: str = Header(None, alias="Device-Model"),
    app_source: str = Header(None, alias="X-App-Source"),
    is_vm: bool = Header(None),
    is_rooted: bool = Header(None),
    db: Session = Depends(get_pg_db),
    user=Security(get_entity_user_for_attendance_2),
    minio_ssd_client=Depends(get_minio_ssd_client),
):
    capture_time = datetime.fromtimestamp(attendance_data.timestamp)
    current_time = datetime.now()
    if current_time.day > 5 and current_time.month != capture_time.month:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O'tgan oyning davomati qabul qilinmaydi!")
    app_source = app_source or "PlayMarket"
    if user.tenant_id == 18 and app_source == "PlayMarket" and (not app_version_code or int(app_version_code) < 1169):
        raise HTTPException(
            status_code=status.HTTP_426_UPGRADE_REQUIRED, detail="Ilova versiyasi eski, iltimos ilovani yangilang!"
        )
    access_token = request.headers.get("Authorization", "").split(" ")[-1]
    payload = extract_jwt_token(access_token)
    attestation_unique_id = payload.get("attestation_id", None)
    token_id = payload.get("token_id")
    if token_id:
        attestation = get_attestation2(db, user.id, token_id)
    else:
        attestation = get_attestation(db, user.id, access_token, attestation_unique_id)

    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id, TenantEntity.spoofing_threshold, TenantEntity.signature_key)
        .filter_by(id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found.")
    is_valid = False
    if x_signature:
        try:
            # body_bytes = await request.body()
            # payload = body_bytes.decode("utf-8")
            payload = json.dumps(attendance_data.__dict__)
            s_key = base64.b64encode(tenant_entity.signature_key.encode("utf-8")).decode("utf-8")
            is_valid = verify_api_signature(payload, x_signature, s_key)
            if not is_valid:
                pass
                # logger.warning("Invalid signature.")
            else:
                is_valid = True
                logger.info("Signature successfully verified.")
        except UnicodeDecodeError:
            logger.warning("Payload is not valid UTF-8.")
    identity = (
        db.query(Identity).filter_by(id=attendance_data.identity_id, tenant_entity_id=user.tenant_entity_id).first()
    )
    mismatch_entity = False
    if not identity:
        identity = db.query(Identity).filter_by(id=attendance_data.identity_id).first()
        if not identity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
        mismatch_entity = True
    image_url = None
    file_name = f"{attendance_data.identity_id}/{uuid.uuid4()}.jpg"
    if attendance_data.image != "":
        try:
            image_data = base64.b64decode(attendance_data.image)
            image_file = io.BytesIO(image_data)
            acl = "public-read"
            minio_ssd_client.put_object(
                BUCKET_IDENTITY_ATTENDANCE,
                file_name,
                image_file,
                len(image_data),
                content_type="image/jpeg",
                metadata={"x-amz-acl": acl},
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Image is not valid to upload minio, error: {e}"
            ) from e
        image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST3}/{BUCKET_IDENTITY_ATTENDANCE}/{file_name}"
    package = db.query(Package).filter_by(uuid=attendance_data.package_id, is_active=True).first()
    allowed_mtts = db.query(AllowedEntity).filter_by(is_active=True).all()
    allowed_entity_ids = [item.tenant_entity_id for item in allowed_mtts] if allowed_mtts else []
    if (
        package
        and user.tenant_id == 18
        and package.appLicensingVerdict == "UNEVALUATED"
        and tenant_entity.id not in allowed_entity_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_451_UNAVAILABLE_FOR_LEGAL_REASONS, detail="Not licensed application."
        )
    data = {
        "attendance_type": "enter",
        "attendance_datetime": capture_time,
        "snapshot_url": image_url,
        "identity_id": identity.id,
        "tenant_id": identity.tenant_id,
        "tenant_entity_id": user.tenant_entity_id,
        "comp_score": attendance_data.comp_score or 0.0,
        "by_mobile": True,
        "lat": attendance_data.lat,
        "lon": attendance_data.lon,
        "app_version_code": app_version_code,
        "app_version_name": app_version_name,
        "device_id": device_id,
        "device_name": device_name,
        "device_model": device_model,
        "device_ip": device_ip,
        "is_vm": is_vm,
        "is_rooted": is_rooted,
        "is_valid_signature": is_valid,
        "bucket_name": BUCKET_IDENTITY_ATTENDANCE if image_url else None,
        "object_name": file_name if image_url else None,
        "position_id": attendance_data.position_id,
        "attestation_id": attestation.id if attestation else None,
        "package_id": package.id if package else None,
        "package_uuid": attendance_data.package_id,
        "mismatch_entity": mismatch_entity,
        "token_id": token_id,
        "username": user.email,
        "app_source": app_source,
    }
    identity_attendance = Attendance(**data)
    db.add(identity_attendance)
    db.commit()
    db.refresh(identity_attendance)

    if identity.is_active is False or image_url is None or mismatch_entity:
        return identity_attendance
    package_verified = False
    if package:  # noqa
        if package.appLicensingVerdict == "LICENSED" and package.appRecognitionVerdict == "PLAY_RECOGNIZED":  # noqa
            package_verified = True
    express_data = {
        "identity_id": int(str(identity.external_id)),
        "identity_group": identity.identity_group,
        "mtt_id": tenant_entity.external_id,
        "group_id": identity.group_id,
        "created_at": capture_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "attendance_id": identity_attendance.id,
        "position_id": identity_attendance.position_id,
        "lat": float(identity_attendance.lat) or 0.0,
        "lon": float(identity_attendance.lon) or 0.0,
        "app_version": app_version_name,
        "device_model": device_model,
        "device_ip": device_ip,
        "is_spoofed": None,
        "spoofing_score": None,
        "spoofing_bucket": BUCKET_IDENTITY_ATTENDANCE,
        "spoofing_object_name": file_name,
        "tenant_id": identity.tenant_id,
        "image_url": image_url,
        "package_uuid": identity_attendance.package_uuid,
        "version": identity_attendance.version,
        "package_verified": package_verified,
        "username": user.email,
    }
    send_express_attendance_batch.delay(data=express_data)

    attendance_spoofing = AttendanceAntiSpoofing(attendance_id=identity_attendance.id)
    db.add(attendance_spoofing)
    db.commit()
    db.refresh(attendance_spoofing)

    spoofing_task_data = {
        "bucket": BUCKET_IDENTITY_ATTENDANCE,
        "object_name": file_name,
        "lat": attendance_data.lat,
        "lon": attendance_data.lon,
        "app_version_name": app_version_name,
        "device_model": device_model,
        "device_ip": device_ip,
        "identity_id": identity.id,
        "kid_id": identity.external_id,
        "mtt_id": tenant_entity.external_id,
        "created_at": capture_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "attendance_spoofing_id": attendance_spoofing.id,
        "spoofing_threshold": tenant_entity.spoofing_threshold,
        "package_verified": package_verified,
    }

    spoofing_check_task.delay(data=spoofing_task_data)
    return identity_attendance


@mobile_router.get("/attendance", response_model=List[AttendanceInDB])
def get_attendances_without_pagination(
    use_cache: bool = False,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    redis_client=Depends(get_redis_connection),
):
    cache_key = f"attendance:{user.tenant_entity_id}:all"
    if use_cache:
        cached_data = get_from_redis(redis_client, cache_key)
        if cached_data:
            return cached_data
    mobile_attendance = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .filter(
            and_(
                Attendance.tenant_entity_id == user.tenant_entity_id,
                Attendance.by_mobile,
                Attendance.mismatch_entity.is_not(True),
                Attendance.snapshot_url.is_not(None),
            )
        )
        .all()
    )

    max_scores_subquery = (
        db.query(Attendance.identity_id, func.max(Attendance.comp_score).label("max_comp_score"))
        .filter(Attendance.tenant_entity_id == user.tenant_entity_id, Attendance.by_mobile == false())
        .group_by(Attendance.identity_id)
        .subquery()
    )
    attendance_alias = aliased(Attendance)
    smart_camera_attendance = (
        db.query(attendance_alias)
        .join(
            max_scores_subquery,
            and_(
                attendance_alias.identity_id == max_scores_subquery.c.identity_id,
                attendance_alias.comp_score == max_scores_subquery.c.max_comp_score,
            ),
        )
        .options(joinedload(attendance_alias.identity))
        .options(selectinload(attendance_alias.spoofing))
        .options(joinedload(attendance_alias.package))
        .filter(attendance_alias.by_mobile == false())
        .all()
    )

    result = mobile_attendance + smart_camera_attendance
    result = [AttendanceInDB.from_orm(attendance).dict() for attendance in result]
    if use_cache:
        set_to_redis(redis_client, cache_key, result, expire=300)
    return result


@mobile_router.get("/attendance/by_day", response_model=List[AttendanceInDB])
def get_attendance_by_day(
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    use_cache: bool = False,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    redis_client=Depends(get_redis_connection),
):
    cache_key = f"attendance:{user.tenant_entity_id}:{date.strftime('%Y-%m-%d')}"
    if use_cache:
        cached_data = get_from_redis(redis_client, cache_key)
        if cached_data:
            return cached_data
    start_date, end_date = date, date + timedelta(days=1)
    mobile_attendance = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .filter(
            and_(
                Attendance.tenant_entity_id == user.tenant_entity_id,
                Attendance.by_mobile,
                Attendance.attendance_datetime >= start_date,
                Attendance.attendance_datetime < end_date,
                Attendance.mismatch_entity.is_not(True),
                Attendance.snapshot_url.is_not(None),
            )
        )
        .all()
    )

    max_scores_subquery = (
        db.query(Attendance.identity_id, func.max(Attendance.comp_score).label("max_comp_score"))
        .filter(
            Attendance.tenant_entity_id == user.tenant_entity_id,
            Attendance.by_mobile == false(),
            Attendance.attendance_datetime >= start_date,
            Attendance.attendance_datetime < end_date,
        )
        .group_by(Attendance.identity_id)
        .subquery()
    )
    attendance_alias = aliased(Attendance, name="a")
    smart_camera_attendance = (
        db.query(attendance_alias)
        .join(
            max_scores_subquery,
            and_(
                attendance_alias.identity_id == max_scores_subquery.c.identity_id,
                attendance_alias.comp_score == max_scores_subquery.c.max_comp_score,
            ),
        )
        .options(joinedload(attendance_alias.identity))
        .options(selectinload(attendance_alias.spoofing))
        .options(joinedload(attendance_alias.package))
        .filter(
            and_(
                attendance_alias.by_mobile == false(),
                attendance_alias.attendance_datetime >= start_date,
                attendance_alias.attendance_datetime < end_date,
            )
        )
        .all()
    )

    result = mobile_attendance + smart_camera_attendance
    result = [AttendanceInDB.from_orm(attendance).dict() for attendance in result]
    if use_cache:
        set_to_redis(redis_client, cache_key, result, expire=300)
    return result


@mobile_router.get("/attendance/{attendance_id}", response_model=AttendanceDetails)
def get_attendance_details(
    attendance_id: int, db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user_2)
):
    attendance = (
        db.query(Attendance)
        .options(selectinload(Attendance.spoofing))
        .filter_by(id=attendance_id, tenant_entity_id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if not attendance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance not found")
    package_data = None
    if attendance.package_uuid:
        package = get_package_by_uuid(db, str(attendance.package_uuid))
        if package:
            package_data = {
                "appRecognitionVerdict": package.appRecognitionVerdict,
                "appLicensingVerdict": package.appLicensingVerdict,
                "deviceActivityLevel": package.deviceActivityLevel,
                "deviceRecognitionVerdict": package.deviceRecognitionVerdict,
                "playProtectVerdict": package.playProtectVerdict,
                "appsDetected": package.appsDetected,
            }

    similarity_in_area = (
        db.query(SimilarityAttendancePhotoInArea).filter_by(attendance_id=attendance_id, is_active=True).all()
    )
    similarity_in_entity = (
        db.query(SimilarityAttendancePhotoInEntity).filter_by(attendance_id=attendance_id, is_active=True).all()
    )
    similarity_main_photo_in_area = (
        db.query(SimilarityMainPhotoInArea).filter_by(identity_id=attendance.identity_id, is_active=True).all()
    )
    similarity_main_photo_in_entity = (
        db.query(SimilarityMainPhotoInEntity).filter_by(identity_id=attendance.identity_id, is_active=True).all()
    )
    return {
        "spoofing": attendance.spoofing,
        "package": package_data,
        "similarity_in_area": similarity_in_area,
        "similarity_in_entity": similarity_in_entity,
        "similarity_main_photo_in_area": similarity_main_photo_in_area,
        "similarity_main_photo_in_entity": similarity_main_photo_in_entity,
    }


@router.get("/{pk}", response_model=IdentityInDB)
def get_identity(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    identity = db.query(Identity).filter_by(id=pk, tenant_entity_id=user.tenant_entity_id, is_active=is_active).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found") from None
    return identity


@mobile_router.websocket("/ws/relative/{entity_id}")
async def parent_attendance_websocket(websocket: WebSocket, entity_id: int):
    await websocket.accept()

    if entity_id not in rooms:
        rooms[entity_id] = {"data": [], "ws": websocket}

    global entity_users

    try:
        while True:
            data = await websocket.receive_json()
            if data:
                rooms[entity_id]["data"].insert(0, data)
                entity_user = entity_users.get(entity_id)
                if entity_user:
                    try:
                        await entity_user.send_text(json.dumps(data))
                    except Exception as e:
                        logger.info(f"Entity user websocket send_text error: {str(e)}")
    except WebSocketDisconnect:
        logger.info("Relative WebSocket disconnected")
    except Exception as e:
        logger.error(f"Event Websocket error: {str(e)}")


@mobile_router.websocket("/ws/identity/relative/attendance/{entity_id}")
async def entity_user_websocket(websocket: WebSocket, entity_id: int):
    await websocket.accept()

    global entity_users

    if entity_id not in entity_users:
        entity_users[entity_id] = websocket

    try:
        while True:
            pass
    except WebSocketDisconnect:
        logger.info("Entity user websocket disconnected")
        del entity_users[entity_id]


@mobile_router.get("/parent/ws/attendance", response_model=List[ParentAttendanceScheme])
def get_parent_attendance_real_time(limit: int, user=Security(get_tenant_entity_user_2)):
    room = rooms.get(user.tenant_entity_id, None)
    if not room:
        return []
    if not room["data"]:
        return []
    attendances: List[ParentAttendanceScheme] = room["data"]
    result: List[ParentAttendanceScheme] = []
    if limit == 0:
        return []
    i = 0
    now = datetime.now()
    today = datetime(year=now.year, month=now.month, day=now.day)
    for attendance in attendances:
        if i % limit == 0:
            break
        if datetime.fromisoformat(attendance.date) > today:
            i += 1
            result.append(attendance)
    return result


@mobile_router.get("/parent/attendance", response_model=List[ParentAttendanceScheme])
def get_parent_attendance(
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    redis_client=Depends(get_redis_connection),
):
    date = date if date else datetime.today()
    if limit:
        cache_key = f"pattendance:{user.tenant_entity_id}:{date.strftime('%Y-%m-%d')}:{limit}"
    else:
        cache_key = f"pattendance:{user.tenant_entity_id}:{date.strftime('%Y-%m-%d')}:all"
    cache_data = get_from_redis(redis_client, cache_key)
    if cache_data:
        return cache_data
    start_datetime = datetime.combine(date.date(), datetime.min.time())
    end_datetime = datetime.combine(date.date(), datetime.max.time())

    smart_cameras = db.query(SmartCamera).filter_by(tenant_entity_id=user.tenant_entity_id, is_active=True).all()
    s_ids = [smart_camera.id for smart_camera in smart_cameras]

    query = (
        db.query(RelativeAttendance)
        .filter(
            and_(
                RelativeAttendance.smart_camera_id.in_(s_ids),
                RelativeAttendance.attendance_datetime >= start_datetime,
                RelativeAttendance.attendance_datetime <= end_datetime,
            )
        )
        .order_by(RelativeAttendance.attendance_datetime.desc())
        .join(RelativeAttendance.relative)
    )

    if limit:
        query = query.limit(limit)

    results = query.all()

    parent_attendance_schemes = []
    for relative_attendance in results:
        relative = relative_attendance.relative

        # Fetch Identities associated with the Relative and filter by tenant_entity_id
        identities = (
            db.query(Identity)
            .join(IdentityRelative, Identity.id == IdentityRelative.identity_id)
            .filter(
                and_(IdentityRelative.relative_id == relative.id, Identity.tenant_entity_id == user.tenant_entity_id)
            )
            .all()
        )

        if identities:
            identity_bases = [
                IdentityBaseForRelative(
                    first_name=identity.first_name,
                    last_name=identity.last_name,
                    photo=identity.photo,
                    identity_group=identity.identity_group,
                    external_id=identity.external_id,
                    group_id=identity.group_id,
                    group_name=identity.group_name,
                )
                for identity in identities
            ]

            # Prepare RelativeBase
            relative_base = RelativeBase(
                first_name=relative.first_name,
                last_name=relative.last_name,
                photo=relative.photo,
                email=relative.email,
                phone=relative.phone,
                pinfl=relative.pinfl,
            )

            # Construct ParentAttendanceScheme
            parent_attendance_scheme = ParentAttendanceScheme(
                relative=relative_base,
                snapshot_url=relative_attendance.snapshot_url,
                date=relative_attendance.attendance_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                identities=identity_bases,
            )

            parent_attendance_schemes.append(parent_attendance_scheme)

    result = [ParentAttendanceScheme.from_orm(attendance).dict() for attendance in parent_attendance_schemes]
    set_to_redis(redis_client, cache_key, result, expire=600)
    return result


@mobile_router.post("/employee/extra_attendance")
def add_extra_attendance_to_employee(
    identity_id: int,
    data: List[ExtraAttendanceCreate],
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    identity = (
        db.query(Identity).filter_by(id=identity_id, tenant_entity_id=user.tenant_entity_id, is_active=True).first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    if identity.identity_group != 1 or identity.identity_type != "staff":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This identity is not an employee")
    delete_extra_attendances(db, identity_id)
    for position in data:
        new_position = ExtraAttendance(
            identity_id=identity.id,
            position_id=position.position_id,
            position_name=position.position_name,
            week_day=position.week_day,
            start_time=position.start_time,
            end_time=position.end_time,
        )
        db.add(new_position)
        db.commit()
        db.refresh(new_position)
    identity.version += 1
    db.commit()
    db.refresh(identity)
    return identity
