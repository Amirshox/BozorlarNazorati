import time
from typing import Type

from sqlalchemy import and_
from sqlalchemy.orm import Session

from models import Firmware, Identity, Relative, SmartCamera, SmartCameraFirmware, SmartCameraTask, Visitor
from utils.image_processing import image_url_to_base64


def restart_camera_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    """
    lib_platform_version= 'platform v6.0.3'
    if lib_platform_version != data['lib_platform_version']:
        print(f"UPGRADE NEEDED FOR {data['device_id']}")
        return {
              "request_type":"upgrade",
              "request_id": "123456",
              "pass": "123456",
              "URL": "https://s3.realsoft.ai/camerafirmware/10.001.11.1_MAIN_V4.18(240304).img",
              "timestamp": 1706230794
              }
    """

    print(f"Task for restart. Device: {camera.device_id}")
    payload = {"request_id": f"R_{task.id}", "request_type": "restart"}
    task.is_sent = True
    db.commit()
    return payload


def firmware_camera_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    print(f"Task for upgrade. Device: {camera.device_id}")
    firmware = (
        db.query(Firmware)
        .join(SmartCameraFirmware)
        .filter(
            and_(
                SmartCameraFirmware.smart_camera_id == camera.id,
                SmartCameraFirmware.is_active,
                Firmware.is_active,
            )
        )
        .first()
    )
    if firmware:
        payload = {
            "request_id": f"FT_{firmware.id}_{task.id}",
            "request_type": "upgrade",
            "URL": firmware.img,
        }
        task.is_sent = True
        db.commit()
        return payload
    else:
        task.is_active = False
        db.commit()
    return {"request_type": "idleTime", "timestamp": int(time.time())}


def add_identity_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    if task.users:
        print(f"Task for addUser. Device: {camera.device_id}")
        user_list = []
        for item in task.users:
            identity = db.query(Identity).filter_by(id=item.identity_id, is_active=True).first()
            if identity:
                user = {
                    "user_id": str(identity.id),
                    "image_type": "image",
                    "image_content": image_url_to_base64(identity.photo),
                    "user_info": {"name": identity.first_name},
                    "group": identity.identity_group,
                    "user_list": 2,
                }
                user_list.append(user)
        payload = {
            "request_id": f"T_{task.id}",
            "request_type": "addUser",
            "user_list": user_list,
        }
        task.is_sent = True
        db.commit()
        return payload
    return {"request_type": "idleTime", "timestamp": int(time.time())}


def update_identity_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    if task.users:
        print(f"Task for updateUser. Device: {camera.device_id}")
        user_list = []
        for item in task.users:
            identity = db.query(Identity).filter_by(id=item.identity_id, is_active=True).first()
            if identity:
                user = {
                    "user_id": str(identity.id),
                    "image_type": "image",
                    "image_content": image_url_to_base64(identity.photo),
                    "user_info": {"name": identity.first_name},
                    "group": identity.identity_group,
                    "user_list": 2,
                }
                user_list.append(user)
        payload = {
            "request_id": f"UT_{task.id}",
            "request_type": "updateUser",
            "user_list": user_list,
        }
        task.is_sent = True
        db.commit()
        return payload
    return {"request_type": "idleTime", "timestamp": int(time.time())}


def delete_identity_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    if task.users:
        print(f"Task for deleteUser. Device: {camera.device_id}")
        identity = db.query(Identity).filter_by(id=task.users[0].identity_id, is_active=True).first()
        if identity:
            payload = {
                "request_id": f"DT_{task.id}",
                "request_type": "deleteUser",
                "user_id": str(identity.id),
            }
            task.is_sent = True
            db.commit()
            return payload
    return {"request_type": "idleTime", "timestamp": int(time.time())}


def add_visitor_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    if task.users:
        print(f"Task for addVisitor. Device: {camera.device_id}")
        user_list = []
        for item in task.users:
            visitor = db.query(Visitor).filter_by(id=item.visitor_id, is_active=True).first()
            user = {
                "user_id": f"v{visitor.id}",
                "image_type": "image",
                "image_content": image_url_to_base64(visitor.photo),
                "user_info": {"name": "visitor"},
                "group": 1,
                "user_list": 2,
            }
            user_list.append(user)
        payload = {
            "request_id": f"VT_{task.id}",
            "request_type": "addUser",
            "user_list": user_list,
        }
        task.is_sent = True
        db.commit()
        return payload
    return {"request_type": "idleTime", "timestamp": int(time.time())}


def delete_visitor_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    if task.users:
        print(f"Task for deleteVisitor. Device: {camera.device_id}")
        for item in task.users:
            payload = {
                "request_id": f"DVT_{task.id}",
                "request_type": "deleteUser",
                "user_id": f"v{item.visitor_id}",
            }
            task.is_sent = True
            db.commit()
            return payload
    return {"request_type": "idleTime", "timestamp": int(time.time())}


def add_relative_task(db: Session, task: Type[SmartCameraTask], camera: Type[SmartCamera]):
    if task.users:
        print(f"Task for addRelative. Device: {camera.device_id}")
        user_list = []
        for item in task.users:
            relative = db.query(Relative).filter_by(id=item.relative_id, is_active=True).first()
            user = {
                "user_id": f"r{relative.id}",
                "image_type": "image",
                "image_content": image_url_to_base64(relative.photo),
                "user_info": {"name": relative.first_name},
                "group": 3,
                "user_list": 2,
            }
            user_list.append(user)
        payload = {
            "request_id": f"IRT_{task.id}",
            "request_type": "addUser",
            "user_list": user_list,
        }
        task.is_sent = True
        db.commit()
        return payload
    return {"request_type": "idleTime", "timestamp": int(time.time())}
