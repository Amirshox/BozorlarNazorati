import logging
import os
import requests

from fastapi import APIRouter, Depends, Header, HTTPException
from typing import List, Literal
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_
from sqlalchemy.orm import Session
from starlette import status

from auth.oauth2 import get_current_relative
from config import NODAVLAT_BOGCHA_BASE_URL, NODAVLAT_BOGCHA_PASSWORD, NODAVLAT_BOGCHA_USERNAME
from database import db_relative
from database.database import get_pg_db
from database.minio_client import get_minio_client
from models import (
    Identity,
    IdentityRelative,
    MetricsSeria,
    Notification,
    Relative,
    RelativeFCMToken,
    TenantEntity,
    User,
    UserFCMToken,
)
from schemas.identity import IdentityInDBForRelative, MetricsSeriaBase, NotificationInDB, SimpleResponse
from schemas.relative.base import RelativeMeSchema, UserSetPasswordResponse, RelativeChildrenResponse, \
    NotificationNotFoundKassa_idData
from services.notification import FirebaseNotificationService, cert_one_system
from services.relative.reset import relative_reset_service
from services.wservice import get_parent_info
from tasks import child_implementation_task
from utils.pagination import CustomPage

router = APIRouter(prefix="", tags=["main"])

notification_service_one_system = FirebaseNotificationService(cert_one_system)

RELATIVE_IDENTITY_BUCKET = os.getenv("MINIO_RELATIVE_IDENTITY", "relative-identity")

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")

logger = logging.getLogger(__name__)

if not get_minio_client().bucket_exists(RELATIVE_IDENTITY_BUCKET):
    get_minio_client().make_bucket(RELATIVE_IDENTITY_BUCKET)

@router.put("/login/fcm_token", response_model=SimpleResponse)
def set_fcm_token(
    token: str,
    device_id: str = Header(None, alias="Device-Id"),
    db: Session = Depends(get_pg_db),
    relative: Relative = Depends(get_current_relative),
):
    fcm_token = (
        db.query(RelativeFCMToken).filter_by(relative_id=relative.id, device_id=device_id, is_active=True).first()
    )
    if fcm_token:
        fcm_token.token = token
        db.commit()
        db.refresh(fcm_token)
    else:
        new_fcm_token = RelativeFCMToken(relative_id=relative.id, device_id=device_id, token=token)
        db.add(new_fcm_token)
        db.commit()
        db.refresh(new_fcm_token)
    return {"success": True, "message": None}


@router.put("/logout/fcm_token", response_model=SimpleResponse)
def delete_fcm_token(
    device_id: str = Header(None, alias="Device-Id"),
    db: Session = Depends(get_pg_db),
    relative: Relative = Depends(get_current_relative),
):
    fcm_token = (
        db.query(RelativeFCMToken).filter_by(relative_id=relative.id, device_id=device_id, is_active=True).first()
    )
    if fcm_token:
        fcm_token.is_active = False
        db.commit()
        db.refresh(fcm_token)
    return {"success": True, "message": None}


@router.post("/reset", response_model=UserSetPasswordResponse)
def user_set_password(
    new_password: str, relative: Relative = Depends(get_current_relative), db: Session = Depends(get_pg_db)
):
    return relative_reset_service(db, relative, new_password)


@router.get("/me", response_model=RelativeMeSchema)
def get_relative_me(relative: Relative = Depends(get_current_relative)):
    return relative


@router.post("/add-identity", response_model=IdentityInDBForRelative)
def add_relative_identity(
    pinfl: str, db: Session = Depends(get_pg_db), relative: Relative = Depends(get_current_relative)
):
    identity = db.query(Identity).filter_by(pinfl=pinfl, identity_group=0, is_active=True).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bola topilmadi!")
    identity_relative = (
        db.query(IdentityRelative).filter_by(identity_id=identity.id, relative_id=relative.id, is_active=True).first()
    )
    if not identity_relative:
        parent_data = get_parent_info(pinfl)
        if relative.pinfl in [parent_data["father_pinfl"], parent_data["mother_pinfl"]]:
            new_relation = IdentityRelative(identity_id=identity.id, relative_id=relative.id)
            db.add(new_relation)
            db.commit()
            db.refresh(new_relation)
            return identity
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bola sizga tegishli emas!")
    return identity


@router.get("/children", response_model=RelativeChildrenResponse)
def get_relative_children(db: Session = Depends(get_pg_db), relative: Relative = Depends(get_current_relative)):
    r = requests.get(
        url=NODAVLAT_BOGCHA_BASE_URL + f"parent_fees/mtt/data?pinfl={relative.pinfl}",
        auth=(NODAVLAT_BOGCHA_USERNAME, NODAVLAT_BOGCHA_PASSWORD),
    )
    if r.status_code == 200:
        try:
            data = r.json()["data"]
            if data:
                child_implementation_task.delay(relative.id, data)
                return {"from_api": data, "from_db": None}
        except Exception as e:
            print(f"Error getting children data: {e}")
    children = db_relative.get_relative_children(db, relative.id)
    for child in children:
        entity = child.tenant_entity
        if not child.tenant_entity.kassa_id:
            db_entity = db.query(TenantEntity).filter_by(id=entity.id, is_active=True).first()
            r = requests.get(
                url=NODAVLAT_BOGCHA_BASE_URL + f"mtt/merchant/data?mtt_id={entity.external_id}",
                auth=(NODAVLAT_BOGCHA_USERNAME, NODAVLAT_BOGCHA_PASSWORD),
            )
            if r.status_code == 200:
                try:
                    data = r.json()["data"]
                    child.tenant_entity.kassa_id = data["kassa_id"]
                    if data["kassa_id"]:
                        db_entity.kassa_id = data["kassa_id"]
                        db.commit()
                        db.refresh(db_entity)
                except Exception as e:
                    print(f"Error getting kassa id: {e}")
    return {"from_api": None, "from_db": children}


@router.post("/send/notification/not_found/kassa_id", response_model=SimpleResponse)
def send_notification_not_found_kassa_id(
    type: Literal["comissioner", "merchant"],
    data: NotificationNotFoundKassa_idData,
    db: Session = Depends(get_pg_db),
    relative: Relative = Depends(get_current_relative),
):
    tenant_entity = (
        db.query(TenantEntity.id)
        .filter(
            and_(TenantEntity.external_id == data.mtt_id, TenantEntity.tenant_id.in_([1, 18]), TenantEntity.is_active)
        )
        .first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    identity = (
        db.query(Identity)
        .filter(
            and_(
                Identity.tenant_entity_id == tenant_entity.id,
                Identity.tenant_id.in_([1, 18]),
                Identity.identity_group == 0,
                Identity.external_id == str(data.kid_id),
                Identity.is_active,
            )
        )
        .first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    user = db.query(User).filter_by(tenant_entity_id=tenant_entity.id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    message_title = "Ota-ona to’lov qila olmayapti"
    message_body = (
        "Merchant shartnoma tuzilgan, ammo komissioner emasligingiz sababli ota yoki ona to’lov "
        "qila olmayapti. Iltimos Soliq saytiga yoki ilovasiga kirib komissioner bo’ling."
    )
    new_notification = Notification(
        sender_id=relative.id,
        sender_type="relative",
        receiver_id=user.id,
        receiver_type="user",
        title=message_title,
        body=message_body,
        data={"kid_id": data.kid_id, "mtt_id": data.mtt_id, "type": type},
        image=data.image,
        external_link=data.external_link,
        type_index=1,
    )
    db.add(new_notification)
    db.commit()
    db.refresh(new_notification)
    fcm_tokens = (
        db.query(UserFCMToken).filter_by(user_id=user.id, is_active=True).order_by(UserFCMToken.created_at.desc()).all()
    )
    is_sent_list = []
    if fcm_tokens:
        for fcm_token in fcm_tokens:
            is_sent = notification_service_one_system.send_notification(
                token=fcm_token.token,
                message_title=message_title,
                message_body=message_body,
                data={"kid_id": data.kid_id, "mtt_id": data.mtt_id},
                image=data.image,
                external_link=data.external_link,
            )
            is_sent_list.append(is_sent)
    else:
        print("FCM token not found")
    new_notification.attempt_count += 1
    is_sent = any(is_sent_list)
    if is_sent:
        new_notification.is_sent_via_one_system = True
        db.commit()
    else:
        print("Failed to send notification via one_system, sent to platon")
    r = requests.post(
        url=NODAVLAT_BOGCHA_BASE_URL + f"mtt/notification?mtt_id={data.mtt_id}&type={type}",
        auth=(NODAVLAT_BOGCHA_USERNAME, NODAVLAT_BOGCHA_PASSWORD),
    )
    if r.status_code == 200:
        new_notification.is_sent_via_platon = True
        db.commit()
        return {"success": True, "message": "Notification sent to platon"}
    if is_sent:
        return {"success": True, "message": "Notification sent via one_system"}
    return {"success": False, "message": f"Failed to send notification, error: {r.text}"}


@router.get("/notification/by_kassa_id_not_found", response_model=CustomPage[NotificationInDB])
def get_notification_by_kassa_id_not_found(
    db: Session = Depends(get_pg_db), relative: Relative = Depends(get_current_relative)
):
    query_set = (
        db.query(Notification)
        .filter_by(receiver_id=relative.id, receiver_type="relative", is_active=True)
        .order_by(Notification.created_at.desc())
    )
    return paginate(query_set)


@router.delete("/remove-child/{identity_id}", response_model=SimpleResponse)
def remove_child(
    identity_id: int, db: Session = Depends(get_pg_db), relative: Relative = Depends(get_current_relative)
):
    return {"success": True, "message": "At the moment the API is not working..."}
    # identity_relative = (
    #     db.query(IdentityRelative).filter_by(identity_id=identity_id, relative_id=relative.id, is_active=True).first()
    # )
    # if not identity_relative:
    #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    # identity_relative.is_active = False
    # db.commit()
    # db.refresh(identity_relative)
    # return {"success": True, "message": "Identity disconnected"}


@router.get("/metrics/seria", response_model=List[MetricsSeriaBase])
def get_metrics_seria(db: Session = Depends(get_pg_db), relative: Relative = Depends(get_current_relative)):
    return db.query(MetricsSeria).filter_by(is_active=True).all()
