import uuid
from typing import Type

from sqlalchemy.orm import Session, selectinload

from models import (
    ErrorSmartCamera,
    Integrations,
    SmartCamera,
    SmartCameraFirmware,
    SmartCameraProfileFirmware,
    SmartCameraTask,
    SmartCameraTaskResult,
    SmartCameraTaskUser,
    Visitor,
)
from models.identity import ErrorRelativeSmartCamera, Identity, IdentitySmartCamera, RelativeSmartCamera
from utils.image_processing import get_error_text_from_code


def firmware_task_result(db: Session, camera: Type[SmartCamera], data: dict):
    if data["code"] == 0:
        firmware_id = int(data["request_id"].split("_")[1])
        firmware_scamera = (
            db.query(SmartCameraFirmware)
            .filter_by(firmware_id=firmware_id, smart_camera_id=camera.id, is_active=True)
            .first()
        )
        if firmware_scamera:
            firmware_scamera.is_active = False
            db.commit()
            new_profile_firmware = SmartCameraProfileFirmware(
                profile_id=camera.smart_camera_profile_id, firmware_id=firmware_id
            )
            db.add(new_profile_firmware)
            db.commit()


def delete_visitor_task_result(db: Session, data: dict, task_id: int):
    task = (
        db.query(SmartCameraTask)
        .options(selectinload(SmartCameraTask.users))
        .filter_by(id=task_id, task_type="delete_visitor", is_sent=True, is_active=True)
        .first()
    )
    if task:
        new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
        db.add(new_task_result)
        db.commit()
        for item in task.users:
            visitor = db.query(Visitor).filter_by(id=item.visitor_id, is_active=True).first()
            if visitor:
                visitor.is_active = False
                db.commit()


def add_visitor_task_result(db: Session, data: dict, task_id: int):
    task = (
        db.query(SmartCameraTask)
        .options(selectinload(SmartCameraTask.users))
        .filter_by(id=task_id, task_type="add_visitor", is_active=True, is_sent=True)
        .first()
    )
    if task:
        new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
        db.add(new_task_result)
        db.commit()
        if data["code"] == 0 and task.users:
            for item in task.users:
                visitor = db.query(Visitor).filter_by(id=item.visitor_id, is_active=True).first()
                if visitor:
                    visitor.is_uploaded = True
                    db.commit()


def add_relative_task_result(db: Session, camera: Type[SmartCamera], data: dict, task_id: int):
    task = (
        db.query(SmartCameraTask)
        .options(selectinload(SmartCameraTask.users))
        .filter_by(id=task_id, task_type="add_relative", is_active=True, is_sent=True)
        .first()
    )
    if task:
        new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
        db.add(new_task_result)
        db.commit()
        db.refresh(new_task_result)
        try:
            users = data["resp_list"]
        except KeyError as e:
            print(f"get resp_list from data: error: {e}")
            users = []
        for user in users:
            relative_id = int(user["user_id"][1:])
            if user["code"] == 0:
                relative_smart_camera = RelativeSmartCamera(relative_id=relative_id, smart_camera_id=camera.id)
                db.add(relative_smart_camera)
                db.commit()
                new_task_result.success_count += 1
            else:
                error_camera = ErrorRelativeSmartCamera(
                    smart_camera_id=camera.id,
                    relative_id=relative_id,
                    code=user["code"],
                    text=get_error_text_from_code(user["code"]),
                )
                db.add(error_camera)
                db.commit()
                new_task_result.error_count += 1
        db.commit()


def update_identity_task_result(db: Session, camera: Type[SmartCamera], data: dict, task_id: int):
    new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
    db.add(new_task_result)
    db.commit()
    db.refresh(new_task_result)
    try:
        users = data["resp_list"]
    except KeyError as e:
        print(f"get resp_list from data: error: {e}")
        users = []
    for user in users:
        is_success = False
        message = None
        if user["code"] == 0:
            is_success = True
            message = "Successfully updated"
            new_task_result.success_count += 1
        else:
            new_task_result.error_count += 1
        db.commit()
        db.refresh(new_task_result)
        integration = db.query(Integrations).filter_by(tenant_id=camera.tenant_id, module_id=1, is_active=True).first()
        if integration:
            callback_url = integration.identity_callback_url
            if integration.auth_type.lower() in ["basic", "jwt"] and integration.username and integration.password:
                auth = {
                    "auth": integration.auth_type,
                    "username": integration.username,
                    "password": integration.password,
                }
            elif integration.token:
                auth = {
                    "auth": integration.auth_type,
                    "token": integration.token,
                    "token_type": integration.token_type,
                }
            else:
                auth = None
            identity = db.query(Identity).filter_by(id=int(user["user_id"]), is_active=True).first()
            event_data = {
                "message_id": str(uuid.uuid4()),
                "payload": {
                    "is_success": is_success,
                    "message": message if message else get_error_text_from_code(user["code"]),
                    "code": user["code"],
                    "type": "update",
                    "id": identity.id if identity else None,
                    "identity_first_name": identity.first_name if identity else None,
                    "pinfl": identity.pinfl if identity else None,
                    "version": identity.version if identity else None,
                    "identity_group": identity.identity_group if identity else None,
                    "identity_type": identity.identity_type if identity else None,
                    "external_id": identity.external_id if identity else None,
                    "tenant_entity_id": identity.tenant_entity_id if identity else None,
                    "device_lat": camera.device_lat,
                    "device_long": camera.device_long,
                },
                "auth": auth,
                "callback_url": callback_url,
            }
            return event_data


def delete_identity_task_result(db: Session, camera: Type[SmartCamera], data: dict, task_id: int):
    task = (
        db.query(SmartCameraTask)
        .options(selectinload(SmartCameraTask.users))
        .filter_by(id=task_id, task_type="delete", is_active=True, is_sent=True)
        .first()
    )
    if task:
        new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
        db.add(new_task_result)
        db.commit()
        is_success = False
        message = None
        if data["code"] == 0 and task.users:
            is_success = True
            for item in task.users:
                identity = db.query(Identity).filter_by(id=item.identity_id, is_active=True).first()
                if identity:
                    identity.is_active = False
                    db.commit()
                    db.refresh(identity)
                    message = "Successfully deleted"
        integration = db.query(Integrations).filter_by(tenant_id=camera.tenant_id, module_id=1, is_active=True).first()
        if integration:
            callback_url = integration.identity_callback_url
            if integration.auth_type.lower() in ["basic", "jwt"] and integration.username and integration.password:
                auth = {
                    "auth": integration.auth_type,
                    "username": integration.username,
                    "password": integration.password,
                }
            elif integration.token:
                auth = {
                    "auth": integration.auth_type,
                    "token": integration.token,
                    "token_type": integration.token_type,
                }
            else:
                auth = None
            event_data = {
                "message_id": str(uuid.uuid4()),
                "payload": {
                    "is_success": is_success,
                    "message": message if message else get_error_text_from_code(data["code"]),
                    "code": data["code"],
                    "type": "delete",
                    "id": identity.id if identity else None,
                    "identity_first_name": identity.first_name if identity else None,
                    "pinfl": identity.pinfl if identity else None,
                    "version": identity.version if identity else None,
                    "identity_group": identity.identity_group if identity else None,
                    "identity_type": identity.identity_type if identity else None,
                    "external_id": identity.external_id if identity else None,
                    "tenant_entity_id": identity.tenant_entity_id if identity else None,
                    "device_lat": camera.device_lat,
                    "device_long": camera.device_long,
                },
                "auth": auth,
                "callback_url": callback_url,
            }
            return event_data


def add_identity_task_result(db: Session, camera: Type[SmartCamera], data: dict, task_id: int):
    task = db.query(SmartCameraTask).filter_by(id=task_id, task_type="add", is_active=True, is_sent=True).first()
    if task:
        new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
        db.add(new_task_result)
        db.commit()
        db.refresh(new_task_result)
        try:
            users = data["resp_list"]
        except KeyError as e:
            print(f"get resp_list from data: error: {e}")
            users = []
        is_success = False
        message = ""
        response_code = 400
        identity_id = None
        for user in users:
            response_code = user["code"]
            identity_id = int(user["user_id"])
            if user["code"] == 0:
                task_user = (
                    db.query(SmartCameraTaskUser)
                    .filter_by(task_id=int(str(task.id)), identity_id=identity_id, is_active=True)
                    .first()
                )
                identity_smart_camera = IdentitySmartCamera(
                    identity_id=task_user.identity_id, smart_camera_id=camera.id
                )
                db.add(identity_smart_camera)
                db.commit()
                new_task_result.success_count += 1
                is_success = True
                message = "Successfully identity added"
            else:
                message = get_error_text_from_code(user["code"])
                new_error = ErrorSmartCamera(
                    identity_id=identity_id,
                    error_type="smart_camera",
                    error_message=message,
                    error_code=user["code"],
                    smart_camera_id=camera.id,
                )
                db.add(new_error)
                db.commit()
                db.refresh(new_error)
                new_task_result.error_count += 1
        db.commit()
        db.refresh(new_task_result)
        if identity_id:
            identity = db.query(Identity).filter_by(id=identity_id, is_active=True).first()
            integration = (
                db.query(Integrations).filter_by(tenant_id=identity.tenant_id, module_id=1, is_active=True).first()
            )
            if integration:
                callback_url = integration.identity_callback_url
                if integration.auth_type.lower() in ["basic", "jwt"] and integration.username and integration.password:
                    auth = {
                        "auth": integration.auth_type,
                        "username": integration.username,
                        "password": integration.password,
                    }
                elif integration.token:
                    auth = {
                        "auth": integration.auth_type,
                        "token": integration.token,
                        "token_type": integration.token_type,
                    }
                else:
                    auth = None
                event_data = {
                    "message_id": str(uuid.uuid4()),
                    "payload": {
                        "is_success": is_success,
                        "message": message,
                        "code": response_code,
                        "type": "create",
                        "id": identity_id,
                        "identity_first_name": identity.first_name,
                        "pinfl": identity.pinfl if identity else None,
                        "version": identity.version,
                        "identity_group": identity.identity_group,
                        "identity_type": identity.identity_type,
                        "external_id": identity.external_id if identity else None,
                        "tenant_entity_id": identity.tenant_entity_id,
                        "device_lat": camera.device_lat,
                        "device_long": camera.device_long,
                    },
                    "auth": auth,
                    "callback_url": callback_url,
                }
                return event_data
