import json
import os

import requests
from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm.session import Session

from models import ErrorSmartCamera, Identity, IdentitySmartCamera, SmartCamera
from schemas.identity import IdentitySmartCameraCreate
from utils.image_processing import get_main_error_text, image_url_to_base64
from utils.log import timeit

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")


def get_unload_identities(db: Session, tenant_entity_id: int, smart_camera_id: int):
    subquery = (
        select(IdentitySmartCamera.identity_id)
        .where(and_(IdentitySmartCamera.smart_camera_id == smart_camera_id, IdentitySmartCamera.is_active))
        .distinct()
    )
    return db.query(Identity).filter(
        and_(
            Identity.id.notin_(subquery),
            Identity.photo.is_not(None),
            Identity.tenant_entity_id == tenant_entity_id,
            Identity.is_active,
        )
    )


def get_loaded_identities(db: Session, tenant_entity_id: int, smart_camera_id: int):
    subquery = (
        select(IdentitySmartCamera.identity_id)
        .where(and_(IdentitySmartCamera.smart_camera_id == smart_camera_id, IdentitySmartCamera.is_active))
        .distinct()
    )
    return db.query(Identity).filter(
        and_(Identity.id.in_(subquery), Identity.tenant_entity_id == tenant_entity_id, Identity.is_active)
    )


@timeit
def call_camera_add_user(identity, camera):
    url = f"http://{CAMERA_MANAGER_URL}/device/{camera.device_id}/user_management/addUser"
    payload_dict = {
        "password": camera.password,
        "user_id": identity.id,
        "user_list": 2,
        "image_type": "image",
        "image_content": image_url_to_base64(str(identity.photo)),
        "user_info": {"name": identity.first_name},
        "group": identity.identity_group,
    }
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    if response.status_code != 200:
        return {"success": False, "error": get_main_error_text(response), "status_code": response.status_code}
    return {"success": True, "error": None, "status_code": 200}


def add_identity_to_smart_camera(db: Session, data: IdentitySmartCameraCreate):
    identity = db.query(Identity).filter_by(id=data.identity_id, is_active=True).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    if data.smart_camera_id_list:
        camera_id_list = data.smart_camera_id_list
    elif data.tenant_entity_id:
        scameras = db.query(SmartCamera).filter_by(tenant_entity_id=data.tenant_entity_id, is_active=True).all()
        camera_id_list = [camera.id for camera in scameras]
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart cameras or tenant entity not found")
    if not camera_id_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No cameras found")
    for smart_camera_id in camera_id_list:
        camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
        if not camera:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Smart camera not found with id: {smart_camera_id}"
            )
        camera_response = call_camera_add_user(identity, camera)
        if not camera_response["success"]:
            new_error = ErrorSmartCamera(
                identity_id=data.identity_id,
                smart_camera_id=int(str(smart_camera_id)),
                error_type="smart_camera",
                error_message=camera_response["error"],
                error_code=camera_response["status_code"],
                version=int(str(identity.version)),
            )
            db.add(new_error)
            db.commit()
            db.refresh(new_error)
            continue
        exists_identity_scamera = (
            db.query(IdentitySmartCamera)
            .filter_by(identity_id=data.identity_id, smart_camera_id=smart_camera_id, is_active=True)
            .first()
        )
        if not exists_identity_scamera:
            new_one = IdentitySmartCamera(identity_id=data.identity_id, smart_camera_id=smart_camera_id)
            db.add(new_one)
            db.commit()
            db.refresh(new_one)
    identity = db.query(Identity).filter_by(id=data.identity_id).first()
    return identity


@timeit
def delete_identity_smart_camera(db: Session, identity_id: int):
    identity = db.query(Identity).filter_by(id=identity_id, is_active=True).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    identity_scameras = db.query(IdentitySmartCamera).filter_by(identity_id=identity_id, is_active=True).all()
    for identity_scamera in identity_scameras:
        camera = db.query(SmartCamera).filter_by(id=identity_scamera.smart_camera_id, is_active=True).first()
        if not camera:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
        url = f"http://{CAMERA_MANAGER_URL}/device/{camera.device_id}/user_management/deleteUser"
        password = camera.password
        payload = json.dumps(
            {"password": password, "user_id": identity_id, "user_list": 2, "group": identity.identity_group}
        )
        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
        )
        if response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response.text)
        identity_scamera.is_active = False
        db.commit()
        db.refresh(identity_scamera)
    return identity
