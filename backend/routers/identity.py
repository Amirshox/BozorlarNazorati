import base64
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from math import ceil
from typing import List, Literal, Optional

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Security, status
from fastapi_pagination.ext.sqlalchemy import paginate
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload, selectinload

from auth.oauth2 import get_current_tenant_admin
from config import (
    CAMERA_MANAGER_BASIC,
    CAMERA_MANAGER_PASSWORD,
    CAMERA_MANAGER_URL,
    MTT_BASIC_PASSWORD,
    MTT_BASIC_USERNAME,
)
from database import db_attendance, db_identity, db_identity_smart_camera, db_region, db_tenant_entity
from database.database import get_pg_db
from database.db_identity import get_package_by_uuid
from database.db_smartcamera import create_task_to_scamera
from database.minio_client import get_minio_ssd_client
from models import (
    ErrorSmartCamera,
    Notification,
    SimilarityAttendancePhotoInArea,
    SimilarityAttendancePhotoInEntity,
    SimilarityMainPhotoInArea,
    SmartCamera,
    TenantEntity,
    User,
    UserFCMToken,
)
from models.identity import Attendance, AttendanceAntiSpoofing, AttendanceReport, Identity, IdentityPhoto
from schemas.attendance import AttendanceDetails, AttendanceInDB, AttendanceReportInDB
from schemas.identity import (
    AttendanceAnalysis,
    CheckIdentitySmartCamera,
    IdentityBaseForPlaton,
    IdentityCreate,
    IdentityInDB,
    IdentityLabelingStatusResponse,
    IdentityPhotoForLabeling,
    IdentitySmartCameraCreate,
    IdentitySmartCameraInDB,
    IdentityUpdate,
    SimpleResponse,
)
from services.notification import FirebaseNotificationService, cert_one_system
from tasks import (
    add_identity_by_task,
    add_identity_to_camera,
    delete_identity_from_smart_camera,
)
from utils.image_processing import MINIO_HOST3, get_image_from_query, is_image_url, make_minio_url_from_image
from utils.kindergarten import BASIC_AUTH
from utils.log import timeit
from utils.pagination import CustomPage

notification_service_one_system = FirebaseNotificationService(cert_one_system)

router = APIRouter(prefix="/identity", tags=["identity"])

IDENTITY_BUCKET = os.getenv("MINIO_BUCKET_IDENTITY", "identity")

NODAVLAT_BASE_URL = os.getenv("NODAVLAT_BASE_URL")

global_minio_ssd_client = get_minio_ssd_client()
if not global_minio_ssd_client.bucket_exists(IDENTITY_BUCKET):
    global_minio_ssd_client.make_bucket(IDENTITY_BUCKET)


logger = logging.getLogger(__name__)


class NotifyMttData(BaseModel):
    mtt_id: int
    message_title: str
    message_body: str


@router.post("/notify/mtt/users")
def notify_mtt_users(
    data: NotifyMttData, db: Session = Depends(get_pg_db), auth: str = Header(None, alias="X-Authorization")
):
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    u, p = base64.b64decode(auth.split(" ")[1]).decode("utf-8").split(":")
    if u == MTT_BASIC_USERNAME and p == MTT_BASIC_PASSWORD:
        tenant_entity = (
            db.query(TenantEntity.id, TenantEntity.external_id)
            .filter_by(external_id=data.mtt_id, is_active=True)
            .first()
        )
        if not tenant_entity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
        users = db.query(User.id).filter(and_(User.tenant_entity_id == tenant_entity.id, User.is_active)).all()
        sent_count = 0
        for user in users:
            new_notification = Notification(
                sender_id=19,
                sender_type="tenant_admin",
                receiver_id=user.id,
                receiver_type="user",
                title=data.message_title,
                body=data.message_body,
                data={"mtt_id": data.mtt_id},
            )
            db.add(new_notification)
            db.commit()
            db.refresh(new_notification)
            fcm_tokens = (
                db.query(UserFCMToken)
                .filter_by(user_id=user.id, is_active=True)
                .order_by(UserFCMToken.created_at.desc())
                .limit(3)
                .all()
            )
            is_sent_list = []
            if fcm_tokens:
                for fcm_token in fcm_tokens:
                    is_sent = notification_service_one_system.send_notification(
                        token=fcm_token.token,
                        message_title=data.message_title,
                        message_body=data.message_body,
                        data={"mtt_id": data.mtt_id},
                    )
                    is_sent_list.append(is_sent)
            else:
                print("FCM token not found")
            new_notification.attempt_count += 1
            is_sent = any(is_sent_list)
            if is_sent:
                new_notification.is_sent_via_one_system = True
                db.commit()
                sent_count += 1
        return {"success": True, "message": f"Notification sent to {sent_count} users", "users_count": len(users)}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


@router.post("/passport/verification/result")
def set_passport_verification_result(data: dict, db: Session = Depends(get_pg_db)):
    result = data.get("result", {})
    _uuid = result.get("uuid", "")
    is_authenticated = result.get("is_authenticated")

    if not _uuid.startswith("identity_photo."):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown uuid")

    if is_authenticated is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request") from None

    try:
        _id = _uuid.split(".")[-1]
        _id = int(_id)
    except (IndexError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bad request") from None

    identity_photo = db.query(IdentityPhoto).filter_by(id=_id, is_active=True).first()
    if identity_photo is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity photo not found")

    identity_photo.passport_verification_result = is_authenticated
    db.commit()
    db.refresh(identity_photo)
    print("Set passport verification result successfully")
    return {"success": True}


@router.post("/answer/attendance/report/{report_id}", response_model=SimpleResponse)  # special for Asadbek
def answer_attendance_report(
    report_id: int,
    _status: Literal["ACCEPTED", "REJECTED"],
    db: Session = Depends(get_pg_db),
    auth: str = Header(None, alias="X-Authorization"),
):
    if not auth:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    u, p = base64.b64decode(auth.split(" ")[1]).decode("utf-8").split(":")
    if u == MTT_BASIC_USERNAME and p == MTT_BASIC_PASSWORD:
        cc = "qabul qilindi" if _status == "ACCEPTED" else "rad etildi"
        message_title = f"Davomat {cc}"
        message_body = f"Davomat ma'sullar tomonidan ko'rib chiqildi. Davomat {cc}"
        report = db.query(AttendanceReport).filter_by(id=report_id, is_active=True).first()
        if not report:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance report not found")
        report.status = _status
        report.moderator_note = message_body
        db.commit()
        db.refresh(report)
        attendance = db.query(Attendance).filter_by(id=report.attendance_id, is_active=True).first()
        if not attendance:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance not found")
        if _status == "ACCEPTED":
            attendance.version += 1
            attendance.has_warning = False
            db.commit()
            db.refresh(attendance)
            spoofing = db.query(AttendanceAntiSpoofing).filter_by(attendance_id=attendance.id, is_active=True).first()
            if spoofing:
                spoofing.score = -1.0
                spoofing.is_spoofed = False
                db.commit()
        user = db.query(User).filter_by(id=report.user_id, is_active=True).first()
        new_notification = Notification(
            sender_id=19,
            sender_type="tenant_admin",
            receiver_id=user.id,
            receiver_type="user",
            title=message_title,
            body=message_body,
            data={"report_id": report.id, "status": report.status},
            type_index=2,
        )
        db.add(new_notification)
        db.commit()
        db.refresh(new_notification)
        fcm_tokens = (
            db.query(UserFCMToken)
            .filter_by(user_id=user.id, is_active=True)
            .order_by(UserFCMToken.created_at.desc())
            .limit(3)
            .all()
        )
        is_sent_list = []
        if fcm_tokens:
            for fcm_token in fcm_tokens:
                is_sent = notification_service_one_system.send_notification(
                    token=fcm_token.token,
                    message_title=message_title,
                    message_body=message_body,
                    data={"report_id": report.id, "status": report.status},
                )
                is_sent_list.append(is_sent)
        else:
            print("FCM token not found")
        new_notification.attempt_count += 1
        is_sent = any(is_sent_list)
        if is_sent:
            new_notification.is_sent_via_one_system = True
            db.commit()
            return {"success": True, "message": "Notification sent via one_system"}
        return {"success": False, "message": "Failed to send notification"}
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


@router.get("/all/by_mtt_id", response_model=List[IdentityBaseForPlaton])
def get_identities_by_mtt_id(
    mtt_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    tenant_entity = (
        db.query(TenantEntity.id)
        .filter_by(external_id=mtt_id, tenant_id=tenant_admin.tenant_id, is_active=True)
        .first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    identities = db_identity.get_identities_by_entity_id(db, tenant_entity.id).all()
    return identities


@router.put("/delete/emb_crop/{pk}", response_model=IdentityInDB)
def delete_identity_photo(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    identity = db.query(Identity).filter_by(id=pk, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    identity.embedding = None
    identity.cropped_image = None
    identity.embedding512 = None
    identity.cropped_image512 = None
    identity.version += 1
    db.commit()
    db.refresh(identity)
    return identity


@router.put("/attendance_report/{report_id}", response_model=AttendanceReportInDB)
def update_attendance_report(
    report_id: int,
    _status: Literal["ACCEPTED", "REJECTED"],
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    report = db.query(AttendanceReport).filter_by(id=report_id, is_active=True).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance report not found")
    report.status = _status
    db.commit()
    db.refresh(report)
    if _status == "ACCEPTED":
        attendance = db.query(Attendance).filter_by(id=report.attendance_id, is_active=True).first()
        if attendance:
            attendance.version += 1
            attendance.has_warning = False
            db.commit()
            db.refresh(attendance)
    return report


@router.get("/attendance_reports", response_model=CustomPage[AttendanceReportInDB])
def get_attendance_reports(
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    tenant_entity_id: Optional[int] = None,
    start_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    end_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = (
        db.query(AttendanceReport)
        .join(Attendance, Attendance.id == AttendanceReport.attendance_id)
        .join(TenantEntity, TenantEntity.id == Attendance.tenant_entity_id)
        .filter(
            and_(
                AttendanceReport.created_at >= start_date,
                AttendanceReport.created_at < end_date,
                TenantEntity.is_active,
                Attendance.is_active,
            )
        )
    )
    if tenant_entity_id:
        tenant_entity = db_tenant_entity.get_tenant_entity(db, tenant_admin.tenant_id, tenant_entity_id)
        query_set = query_set.filter(TenantEntity.id == tenant_entity.id)
    elif district_id:
        query_set = query_set.filter(TenantEntity.district_id == district_id)
    elif region_id:
        query_set = query_set.filter(TenantEntity.region_id == region_id)
    return paginate(query_set)


class MttAttendanceData(BaseModel):
    kid_id: int
    mtt_id: int
    group_id: int | None = None
    visit_date: str | None = None
    is_spoofed: bool | None = None
    bucket: str | None = None
    object_name: str | None = None


class AttendanceCompareResponse(BaseModel):
    id: int
    mtt_id: int
    platon: List[MttAttendanceData] | None = None
    one_system: List[AttendanceInDB] | None = None


@router.get("/mtt/daily/attendance/difference", response_model=AttendanceCompareResponse)
def get_mtt_daily_attendance_difference(
    tenant_entity_id: int,
    visit_date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    only_difference: bool = Query(True, alias="only_difference"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id)
        .filter_by(id=tenant_entity_id, tenant_id=tenant_admin.tenant_id, is_active=True)
        .first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    r = requests.get(
        url=NODAVLAT_BASE_URL + "api/v1/realsoftai/mtt/visits",
        headers=BASIC_AUTH,
        params={"mtt_id": tenant_entity.external_id, "visit_date": visit_date.strftime("%Y-%m-%d")},
    )
    if r.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!")
    remote_data = r.json()["data"]
    remote_data = remote_data["kids"] + remote_data["edus"]
    data = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .filter(
            and_(
                Attendance.tenant_entity_id == tenant_entity.id,
                Attendance.attendance_datetime >= visit_date,
                Attendance.attendance_datetime < visit_date + timedelta(days=1),
            )
        )
        .distinct(Attendance.identity_id)
        .all()
    )
    if only_difference:
        remote_kid_ids = [item["kid_id"] for item in remote_data]
        kid_ids = [item.identity.external_id for item in data]
        new_remote_data = [item for item in remote_data if str(item["kid_id"]) not in kid_ids]
        new_data = [item for item in data if int(item.identity.external_id) not in remote_kid_ids]
        return {
            "id": tenant_entity_id,
            "mtt_id": tenant_entity.external_id,
            "platon": new_remote_data,
            "one_system": new_data,
        }
    return {"id": tenant_entity_id, "mtt_id": tenant_entity.external_id, "platon": remote_data, "one_system": data}


@router.post("/mtt/send/attendance/difference", response_model=SimpleResponse)
def send_mtt_daily_attendance_difference(
    attendance_ids: List[int],
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    attendances = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .filter(Attendance.id.in_(attendance_ids), Attendance.tenant_id == tenant_admin.tenant_id)
        .all()
    )
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id, TenantEntity.tenant_id)
        .filter_by(id=attendances[0].tenant_entity_id, is_active=True)
        .first()
    )
    data_kids = []
    data_edus = []
    for attendance in attendances:
        item = {
            "identity_id": int(attendance.identity.external_id),
            "identity_group": attendance.identity.identity_group,
            "mtt_id": tenant_entity.external_id,
            "group_id": attendance.identity.group_id,
            "created_at": attendance.attendance_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
            "attendance_id": attendance.id,
            "position_id": attendance.position_id,
            "lat": attendance.lat,
            "lon": attendance.lon,
            "app_version": attendance.app_version_name,
            "device_model": attendance.device_model,
            "device_ip": attendance.device_ip,
            "is_spoofed": attendance.spoofing.is_spoofed if attendance.spoofing else False,
            "spoofing_score": attendance.spoofing.score if attendance.spoofing else 0,
            "spoofing_bucket": attendance.bucket_name,
            "spoofing_object_name": attendance.object_name,
            "tenant_id": attendance.tenant_id,
        }
        if attendance.identity.identity_group == 0:
            data_kids.append(item)
        else:
            data_edus.append(item)
    try:
        r1 = requests.post(
            url="https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits_batch",
            headers=BASIC_AUTH,
            json={"identity_group": 1, "tenant_id": tenant_entity.tenant_id, "results": data_edus},
        )
        if r1.status_code == 200:
            logger.info(f"id: {tenant_entity.id}, identity_group: 1, count: {len(data_edus)}, SUCCESS POST")
        else:
            logger.info(f"id: {tenant_entity.id}, identity_group: 1, count: {len(data_edus)}, FAILED POST")

        r2 = requests.post(
            url="https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits_batch",
            headers=BASIC_AUTH,
            json={"identity_group": 0, "tenant_id": tenant_entity.tenant_id, "results": data_kids},
        )
        if r2.status_code == 200:
            logger.info(f"id: {tenant_entity.id}, identity_group: 0, count: {len(data_kids)}, SUCCESS POST")
        else:
            logger.info(f"id: {tenant_entity.id}, identity_group: 0, count: {len(data_kids)}, FAILED POST")
    except Exception as e:
        print("Failed to send attendance difference: " + str(e))
    return {"success": True, "message": None}


@router.get("/add_scamera_by_task")
def add_to_smart_camera_by_task(
    smart_camera_id: Optional[int] = None,
    tenant_entity_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    if smart_camera_id:
        smart_camera = (
            db.query(SmartCamera.id, SmartCamera.tenant_entity_id)
            .filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True)
            .first()
        )
        if not smart_camera:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
        add_identity_by_task.delay(smart_camera.tenant_entity_id, smart_camera.id)
        return {"smart_camera_count": 1}
    if tenant_entity_id:
        smart_cameras = db.query(SmartCamera.id).filter_by(tenant_entity_id=tenant_entity_id, is_active=True).all()
        for smart_camera in smart_cameras:
            add_identity_by_task.delay(tenant_entity_id, smart_camera.id)
        return {"smart_camera_count": len(smart_cameras)}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="smart_camera_id and tenant_entity_id were not given!"
    )


@router.get("/labeling/status", response_model=IdentityLabelingStatusResponse)
def identity_labeling_status(
    tenant_entity_id: Optional[int] = None,
    district_id: Optional[int] = None,
    region_id: Optional[int] = None,
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query = (
        db.query(Identity)
        .join(TenantEntity, Identity.tenant_entity_id == TenantEntity.id)
        .filter(and_(TenantEntity.tenant_id == tenant_admin.tenant_id, Identity.is_active, TenantEntity.is_active))
    )

    if tenant_entity_id:
        query = query.filter(Identity.tenant_entity_id == tenant_entity_id)

    elif district_id:
        query = query.filter(TenantEntity.district_id == district_id)

    elif region_id:
        query = query.filter(TenantEntity.region_id == region_id)

    query = query.order_by(Identity.id)
    query_checkeds = query.filter(Identity.labeling_status == 2)
    query_new_photos = query.filter(Identity.labeling_status == 3)

    total = query.count()
    status2 = query_checkeds.count()
    status3 = query_new_photos.count()
    status1 = total - status2 - status3

    pages = ceil(total / size)

    items = query.limit(size).offset((page - 1) * size).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
        "unchecked": status1,
        "checked": status2,
        "changed": status3,
    }


@router.get("/labeling/identity/{pk}/photos", response_model=List[IdentityPhotoForLabeling])
def get_identity_photos(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_identity.get_identity_photo_history(db, pk)


@router.post("/labeling/photos", response_model=SimpleResponse)
def set_labeling_photos(
    identity_id: int,
    data: List[int],
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    db.query(Identity).filter(Identity.id == identity_id).update({"labeling_status": 2})
    db.query(IdentityPhoto).filter(IdentityPhoto.id.in_(data)).update({"labeled": True})
    db.commit()
    return {"success": True, "message": "Photos labeled"}


@router.post("/", response_model=IdentityInDB)
async def create_identity(
    data: IdentityCreate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_ssd_client=Depends(get_minio_ssd_client),
):
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
    identity = db_identity.create_identity(db, tenant_admin.tenant_id, data, recieved_photo_url)
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
    tenant_entity_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    identity_type: Optional[str] = None,
    identity_group: Optional[int] = None,
    version: Optional[int] = None,
    group_id: Optional[int] = None,
    search: Optional[str] = None,
):
    return paginate(
        db_identity.get_identities(
            db=db,
            tenant_id=tenant_admin.tenant_id,
            tenant_entity_id=tenant_entity_id,
            is_active=is_active,
            identity_type=identity_type,
            identity_group=identity_group,
            version=version,
            group_id=group_id,
            search=search,
        )
    )


@router.get("/by_entity/{tenant_entity_id}", response_model=CustomPage[IdentityInDB])
def get_identities_by_entity_id(
    tenant_entity_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return paginate(db_identity.get_identities_by_entity_id(db, tenant_entity_id, is_active))


@router.get("/by_jetson_device/{jetson_device_id}", response_model=CustomPage[IdentityInDB])
def get_identities_by_jetson_device_id(
    jetson_device_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return paginate(db_identity.get_identieis_by_jetson_id(db, jetson_device_id, is_active))


@router.get("/by_smart_camera", response_model=CustomPage[IdentityInDB])
def get_identities_by_smart_camera(
    smart_camera_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return paginate(db_identity.get_identities_by_scamera_id(db, smart_camera_id, is_active))


@router.get("/by_pinfl", response_model=IdentityInDB)
def get_identity_by_pinfl(
    pinfl: str,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    identity = db_identity.get_identity_by_pinfl(db, tenant_admin.tenant_id, pinfl, is_active)
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Identity not found with pinfl {pinfl}")
    return identity


@router.get("/{pk}", response_model=IdentityInDB)
def get_identity(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    identity = db_identity.get_identity(db, tenant_admin.tenant_id, pk, is_active)
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    return identity


@router.put("/{pk}", response_model=IdentityInDB)
async def update_identity(
    pk: int,
    data: IdentityUpdate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_ssd_client=Depends(get_minio_ssd_client),
):
    identity = db.query(Identity).filter_by(id=pk, tenant_id=tenant_admin.tenant_id).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    if identity.recieved_photo_url != data.photo:
        main_image = get_image_from_query(data.photo)
        main_photo_url = make_minio_url_from_image(
            minio_ssd_client, main_image, IDENTITY_BUCKET, data.pinfl, minio_host=MINIO_HOST3
        )
        data.photo = main_photo_url
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

    identity_scamera = db.query(ErrorSmartCamera).filter_by(identity_id=pk, is_active=True).all()
    if identity_scamera:
        for error in identity_scamera:
            db.delete(error)
        db.commit()
    identity = db_identity.update_identity(db, tenant_admin.tenant_id, pk, data)

    smart_camera_ids = (
        db.query(SmartCamera.id).filter_by(tenant_entity_id=identity.tenant_entity_id, is_active=True).all()
    )
    if identity.photo:
        for smart_camera in smart_camera_ids:
            create_task_to_scamera(db, "update", smart_camera.id, identity.id, "identity")
    return identity


@router.delete("/{pk}", response_model=IdentityInDB)
def delete_identity(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    identity_scamera = db.query(ErrorSmartCamera).filter_by(identity_id=pk, is_active=True).all()
    if identity_scamera:
        for error in identity_scamera:
            db.delete(error)
        db.commit()
    identity = db_identity.delete_identity(db, pk)
    smart_cameras = db.query(SmartCamera).filter_by(tenant_entity_id=identity.tenant_entity_id, is_active=True).all()
    try:
        for smart_camera in smart_cameras:
            delete_identity_from_smart_camera.delay(
                identity.id,
                identity.first_name,
                identity.version,
                identity.identity_group,
                smart_camera.id,
                smart_camera.device_id,
                smart_camera.password,
                tenant_admin.tenant_id,
                identity.tenant_entity_id,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Delete identity from camera delay error: {e}"
        ) from e
    return identity


@router.post("/smartcamera/by_entity_id")
def add_unloaded_identities_by_entity_id(
    tenant_entity_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_cameras = db.query(SmartCamera.id).filter_by(tenant_entity_id=tenant_entity_id, is_active=True).all()
    for smart_camera in smart_cameras:
        identities = db_identity_smart_camera.get_unload_identities(db, tenant_entity_id, smart_camera.id).all()
        for identity in identities:
            add_identity_to_camera.delay(
                identity.id,
                identity.first_name,
                identity.photo,
                identity.version,
                identity.identity_group,
                smart_camera.id,
                smart_camera.device_id,
                smart_camera.password,
                tenant_admin.tenant_id,
                identity.tenant_entity_id,
            )
    return {"success": True}


@router.post("/smartcamera", response_model=IdentityInDB)
def add_identity_to_smartcamera(
    data: IdentitySmartCameraCreate, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_identity_smart_camera.add_identity_to_smart_camera(db, data)


@router.delete("/smartcamera/", response_model=IdentitySmartCameraInDB)
def delete_identity_from_smartcamera(
    identity_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_identity_smart_camera.delete_identity_smart_camera(db, identity_id)


@router.get("/smartcamera/unloaded_identities", response_model=CustomPage[IdentityInDB])
def get_unloaded_identities(
    smart_camera_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera.id, SmartCamera.tenant_entity_id)
        .filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True)
        .first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
    query_set = db_identity_smart_camera.get_unload_identities(db, smart_camera.tenant_entity_id, smart_camera.id)
    return paginate(query_set)


@router.get("/smartcamera/loaded_identities", response_model=CustomPage[IdentityInDB])
def get_loaded_identities(
    smart_camera_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera.id, SmartCamera.tenant_entity_id)
        .filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True)
        .first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
    query_set = db_identity_smart_camera.get_loaded_identities(db, smart_camera.tenant_entity_id, smart_camera.id)
    return paginate(query_set)


@router.get("/attendance/analytics", response_model=AttendanceAnalysis)
def get_identity_attendance_analytics(
    tenant_entity_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    result = AttendanceAnalysis()
    attendances = db_attendance.get_yesterday_attendances_by_entity_id(db, tenant_admin.tenant_id, tenant_entity_id)
    for attendance in attendances:
        if not attendance.comp_score:
            continue
        if attendance.comp_score >= 90:
            result.above_threshold += 1
        elif attendance.comp_score > 0:
            result.below_threshold += 1
    result.total = result.below_threshold + result.above_threshold
    if result.total != 0:
        result.percentage = "%.2f" % (result.above_threshold / result.total * 100)
    return result


@router.get("/attendance/{identity_id}", response_model=CustomPage[AttendanceInDB])
def get_attendances(
    identity_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    query_set = db_attendance.get_attendances(db, identity_id)
    return paginate(query_set)


@router.get("/attendance/details/{attendance_id}", response_model=AttendanceDetails)
def get_attendance_details(
    attendance_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    attendance = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .filter_by(id=attendance_id, is_active=True)
        .first()
    )
    if not attendance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance not found")
    package_data = None
    if attendance.package_id:
        package = get_package_by_uuid(db, str(attendance.package_id))
        if package:
            package_data = {
                "appRecognitionVerdict": package.appRecognitionVerdict,
                "appLicensingVerdict": package.appLicensingVerdict,
                "deviceActivityLevel": package.deviceActivityLevel,
                "deviceRecognitionVerdict": package.deviceRecognitionVerdict,
                "playProtectVerdict": package.playProtectVerdict,
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
    return {
        "spoofing": attendance.spoofing,
        "similarity_in_area": similarity_in_area,
        "similarity_in_entity": similarity_in_entity,
        "similarity_main_photo_in_area": similarity_main_photo_in_area,
        "package": package_data,
    }


@timeit
def process_smart_camera(smart_camera, image_data):
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/user_management/picRecognition"
    payload_dict = {
        "password": smart_camera.password,
        "image_type": "image",
        "image_content": image_data,
        "min_fscore": 80,
        "max_result_num": 5,
    }
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    return smart_camera.tenant_entity_id, response


def get_tenant_entities_with_user_list(tenant_entities, image_data):
    futures = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        for tenant_entity in tenant_entities:
            for smart_camera in tenant_entity.smart_cameras:
                futures.append(executor.submit(process_smart_camera, smart_camera, image_data))

        tenant_entity_status = {
            tenant_entity.id: {
                "tenant_entity": tenant_entity,
                "user_list": None,
                "message": "Smart Cameras are offline",
            }
            for tenant_entity in tenant_entities
        }

        for future in as_completed(futures):
            tenant_entity_id, response = future.result()
            if response.status_code == 200:
                response_json = response.json()
                if response_json.get("code") == 0:
                    tenant_entity_status[tenant_entity_id]["user_list"] = response_json.get("user_list")
                    tenant_entity_status[tenant_entity_id]["message"] = "None"

        result = list(tenant_entity_status.values())

    return result


@router.post("/pic_recognition/smart_camera")
def pic_recognition_smart_camera(
    data: CheckIdentitySmartCamera, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    if data.latitude and data.longitude and data.radius:
        tenant_entities = db_tenant_entity.get_tenant_entities_by_location(
            db, data.latitude, data.longitude, data.radius
        )
    elif data.district:
        district = db_region.search_district(db, search_name=data.district)
        if not district:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such district: {data.district}")
        tenant_entities = db_tenant_entity.get_tenant_entities_by_district_id(db, district.id)
    elif data.region:
        region = db_region.search_region(db, search_name=data.region)
        if not region:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such region: {data.region}")
        tenant_entities = db_tenant_entity.get_tenant_entities_by_region_id(db, region.id)
    elif data.country:
        country = db_region.search_country(db, search_name=data.country)
        if not country:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No such country: {data.country}")
        tenant_entities = db_tenant_entity.get_tenant_entities_by_country_id(db, country.id)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty data found")

    result = get_tenant_entities_with_user_list(tenant_entities, data.image)
    return result
