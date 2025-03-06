import json
import os

import requests
from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import ErrorSmartCamera, SmartCamera, User, UserSmartCamera
from schemas.user import UserSmartCameraBase
from utils.image_processing import image_url_to_base64
from utils.log import timeit

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")


@timeit
def create_user_smart_camera(db: Session, data: UserSmartCameraBase):
    user = db.query(User).filter_by(id=data.user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    camera = db.query(SmartCamera).filter_by(id=data.smart_camera_id, is_active=True).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    try:
        url = f"http://{CAMERA_MANAGER_URL}/device/{camera.device_id}/user_management/addUser"
        payload_dict = {
            "password": camera.password,
            "user_id": user.id,
            "user_list": 2,
            "image_type": "image",
            "image_content": image_url_to_base64(str(user.photo)),
            "user_info": {
                "name": user.first_name,
                "phone_number": user.phone,
            }
        }
        payload = json.dumps(payload_dict)
        response = requests.post(
            url, data=payload,
            headers={'Content-Type': 'application/json'},
            auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD)
        )
        response_dict = json.loads(response.text)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response_dict)
    except Exception as e:
        new_error = ErrorSmartCamera(
            user_id=data.user_id,
            smart_camera_id=data.smart_camera_id,
            error_type="smart_camera",
            error_message=response.text,
            error_code=response.status_code
        )
        db.add(new_error)
        db.commit()
        db.refresh(new_error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create identity smart camera, error: {e}"
        )
    new_one = UserSmartCamera(
        user_id=data.user_id,
        smart_camera_id=data.smart_camera_id
    )
    db.add(new_one)
    db.commit()
    db.refresh(new_one)
    return new_one


@timeit
def delete_user_smart_camera(db: Session, pk: int):
    user_scam = db.query(UserSmartCamera).filter_by(id=pk, is_active=True).first()
    if not user_scam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="UserSmartCamera not found")
    camera = db.query(SmartCamera).filter_by(id=user_scam.smart_camera_id, is_active=True).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    url = f"http://{CAMERA_MANAGER_URL}/device/{camera.device_id}/user_management/deleteUser"
    password = camera.password
    payload = json.dumps({
        "password": password,
        "user_id": user_scam.user_id,
        "user_list": 2,
    })
    response = requests.post(
        url, data=payload,
        headers={'Content-Type': 'application/json'},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD)
    )
    response_dict = json.loads(response.text)
    if response.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response_dict)
    user_scam.is_active = False
    db.commit()
    db.refresh(user_scam)
    return user_scam
