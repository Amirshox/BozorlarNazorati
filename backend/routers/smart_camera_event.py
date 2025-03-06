import base64
import io
import json
import logging
import os
import time
import uuid
from datetime import datetime

import pytz
import sentry_sdk
import websockets
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_
from sqlalchemy.orm import Session, selectinload

from database.database import get_mongo_db, get_pg_db
from database.db_relative import get_relative_identities
from database.db_smartcamera import create_task_to_scamera
from database.minio_client import get_minio_client
from models import (
    District,
    Integrations,
    Room,
    SmartCamera,
    SmartCameraTask,
    SmartCameraTaskResult,
    TenantEntity,
    ThirdPartyIntegration,
    ThirdPartyIntegrationTenant,
    Visitor,
    VisitorAttendance,
    Wanted,
)
from models.face_recognition_mongo_model import FaceRecognitionRequestSchema
from models.identity import (
    Attendance,
    Identity,
    Relative,
    RelativeAttendance,
    WantedAttendance,
)
from services.scamera_task_request import (
    add_identity_task,
    add_relative_task,
    add_visitor_task,
    delete_identity_task,
    delete_visitor_task,
    firmware_camera_task,
    restart_camera_task,
    update_identity_task,
)
from services.scamera_task_result import (
    add_identity_task_result,
    add_relative_task_result,
    add_visitor_task_result,
    delete_identity_task_result,
    delete_visitor_task_result,
    firmware_task_result,
    update_identity_task_result,
)
from tasks import notify_integrator, on_event, send_attendance_to_websocket
from utils.redis_cache import get_from_redis, get_redis_connection, set_to_redis_unlimited

uzbekistan_timezone = pytz.timezone("Asia/Tashkent")

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME")
BUCKET_IDENTITY = os.getenv("MINIO_BUCKET_IDENTITY")
RELATIVE_IDENTITY_BUCKET = os.getenv("MINIO_RELATIVE_IDENTITY", "relative-identity")
BUCKET_VISITOR = os.getenv("MINIO_BUCKET_VISITOR")
WANTED_BUCKET = os.getenv("MINIO_BUCKET_WANTED", "wanted")
BUCKET_USER_ATTENDANCE = os.getenv("MINIO_BUCKET_USER_ATTENDANCE")
MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")

BUCKET_VISITOR_BACKGROUND = "visitor-background"
BUCKET_VISITOR_BODY = "visitor-body"
BUCKET_IDENTITY_BACKGROUND = "identity-background"
BUCKET_IDENTITY_BODY = "identity-body"
BUCKET_WANTED_BACKGROUND = "wanted-background"
BUCKET_WANTED_BODY = "wanted-body"

MINIO_CLEAR_SPOOF = os.getenv("MINIO_CLEAR_SPOOF", "clear-attendance")
MINIO_COMPROMISED_SPOOF = os.getenv("MINIO_COMPROMISED_SPOOF", "compromised-attendance")
BUCKET_IDENTITY_ATTENDANCE = os.getenv("BUCKET_IDENTITY_ATTENDANCE", "identity-attendance")
BUCKET_RELATIVE_ATTENDANCE = os.getenv("BUCKET_RELATIVE_ATTENDANCE", "relative-attendance")

router = APIRouter(prefix="", tags=["smart-camera"])
ENDPOINT = os.getenv("MINIO_ENDPOINT")
WEBSOCKET_URL = os.getenv("WEBSOCKET_URL")

if not get_minio_client().bucket_exists(BUCKET_VISITOR):
    get_minio_client().make_bucket(BUCKET_VISITOR)
if not get_minio_client().bucket_exists(BUCKET_NAME):
    get_minio_client().make_bucket(BUCKET_NAME)
if not get_minio_client().bucket_exists(BUCKET_VISITOR_BACKGROUND):
    get_minio_client().make_bucket(BUCKET_VISITOR_BACKGROUND)
if not get_minio_client().bucket_exists(BUCKET_VISITOR_BODY):
    get_minio_client().make_bucket(BUCKET_VISITOR_BODY)
if not get_minio_client().bucket_exists(BUCKET_IDENTITY_BACKGROUND):
    get_minio_client().make_bucket(BUCKET_IDENTITY_BACKGROUND)
if not get_minio_client().bucket_exists(BUCKET_IDENTITY_BODY):
    get_minio_client().make_bucket(BUCKET_IDENTITY_BODY)
if not get_minio_client().bucket_exists(BUCKET_WANTED_BACKGROUND):
    get_minio_client().make_bucket(BUCKET_WANTED_BACKGROUND)
if not get_minio_client().bucket_exists(BUCKET_WANTED_BODY):
    get_minio_client().make_bucket(BUCKET_WANTED_BODY)
if not get_minio_client().bucket_exists(RELATIVE_IDENTITY_BUCKET):
    get_minio_client().make_bucket(RELATIVE_IDENTITY_BUCKET)
if not get_minio_client().bucket_exists(MINIO_CLEAR_SPOOF):
    get_minio_client().make_bucket(MINIO_CLEAR_SPOOF)
if not get_minio_client().bucket_exists(MINIO_COMPROMISED_SPOOF):
    get_minio_client().make_bucket(MINIO_COMPROMISED_SPOOF)
if not get_minio_client().bucket_exists(BUCKET_IDENTITY_ATTENDANCE):
    get_minio_client().make_bucket(BUCKET_IDENTITY_ATTENDANCE)
if not get_minio_client().bucket_exists(BUCKET_RELATIVE_ATTENDANCE):
    get_minio_client().make_bucket(BUCKET_RELATIVE_ATTENDANCE)

logger = logging.getLogger(__name__)


@router.post("/taskRequest")
async def task_request(
    request: Request,
    db: Session = Depends(get_pg_db),
    mongo_db=Depends(get_mongo_db),
    redis_client=Depends(get_redis_connection),
):
    """
    data = {
        'device_id': 'H010001172B0100010741',
        'device_mac': 'bc-07-18-01-5d-9e',
        'lib_platform_version': 'platform v6.0.2D',
        'software_version': '10.001.11.1_MAIN_V4.13_live(231028)',
        'lib_ai_version': 'ai zx v20231011',
        'device_ip': '192.168.0.168',
        'time_stamp': 1707299321,
        'device_name': 'IPCamera',
        'sign_tby': 'c0af9d851332f21ff2b02981d59fec23'
    }
    """

    def is_changed_camera(_camera, _data) -> bool:
        return (
            _camera.device_ip != _data["device_ip"]
            or _camera.device_mac != _data["device_mac"]
            or _camera.software_version != _data["software_version"]
            or _camera.lib_platform_version != _data["lib_platform_version"]
            or _camera.lib_ai_version != _data["lib_ai_version"]
            or _camera.device_name != _data["device_name"]
        )

    try:
        data = await request.json()
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload") from e

    old_scameras = get_from_redis(redis_client, "connected_scameras") or {}
    old_scameras[data["device_id"]] = data
    set_to_redis_unlimited(redis_client, "connected_scameras", old_scameras)

    camera = db.query(SmartCamera).filter_by(device_id=data["device_id"], is_active=True).first()
    if camera:
        if is_changed_camera(camera, data):
            camera.device_ip = data["device_ip"]
            camera.device_mac = data["device_mac"]
            camera.lib_platform_version = data["lib_platform_version"]
            camera.software_version = data["software_version"]
            camera.lib_ai_version = data["lib_ai_version"]
            camera.device_name = data["device_name"]
            db.commit()
            db.refresh(camera)

        post = {"id": camera.id, "device_id": camera.device_id, "created_at": datetime.now()}
        await mongo_db["analytics"].insert_one(post)

        task = (
            db.query(SmartCameraTask)
            .options(selectinload(SmartCameraTask.users))
            .filter_by(smart_camera_id=camera.id, is_sent=False, is_active=True)
            .first()
        )
        if task:
            if task.task_type == "restart":
                return restart_camera_task(db, task, camera)

            if task.task_type == "assign":
                return firmware_camera_task(db, task, camera)

            if task.task_type == "add":
                return add_identity_task(db, task, camera)

            if task.task_type == "update":
                return update_identity_task(db, task, camera)

            if task.task_type == "delete":
                return delete_identity_task(db, task, camera)

            if task.task_type == "add_visitor":
                return add_visitor_task(db, task, camera)

            if task.task_type == "delete_visitor":
                return delete_visitor_task(db, task, camera)

            if task.task_type == "add_relative":
                return add_relative_task(db, task, camera)

    return {"request_type": "idleTime", "timestamp": int(time.time())}


@router.post("/taskResult")
async def task_result(request: Request, db: Session = Depends(get_pg_db)):
    """
    data = {
        'resp_list': [
            {'user_id': '14218', 'code': 0}
        ],
        'resp_type': 'addUser',
        'request_id': 'T_2',
        'code': 0,
        'device_mac': 'bc-07-18-01-94-0d',
        'deviceID': 'H010001180F0100010019',
        'device_id': 'H010001180F0100010019',
        'log': "'addUser' success",
        'device_ip': '192.168.100.195',
        'sign_tby': '7bd3d9127d45011d0c5dfb229ac62ecf'
    }
    """

    try:
        data = await request.json()
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload") from e

    camera = db.query(SmartCamera).filter_by(device_id=data["device_id"], is_active=True).first()

    request_id_parts = data["request_id"].split("_")
    prefix = request_id_parts[0]
    task_id = int(request_id_parts[-1])

    if prefix == "FT":
        firmware_task_result(db, camera, data)

    elif prefix == "R":
        print(f"Task Result for restart. Device: {camera.device_id}")
        new_task_result = SmartCameraTaskResult(task_id=task_id, status_code=data["code"])
        db.add(new_task_result)
        db.commit()

    elif prefix == "DVT":
        print(f"Task Result for delete_visitor. Device: {camera.device_id}")
        if data["code"] == 0:
            delete_visitor_task_result(db, data, task_id)

    elif prefix == "VT":
        add_visitor_task_result(db, data, task_id)

    elif prefix == "IRT":
        print(f"Task Result for add_relative. Device: {camera.device_id}")
        add_relative_task_result(db, camera, data, task_id)

    elif prefix == "UT":
        event_data = update_identity_task_result(db, camera, data, task_id)
        if event_data:
            on_event(event_data)

    elif prefix == "DT":
        event_data = delete_identity_task_result(db, camera, data, task_id)
        if event_data:
            on_event(event_data)

    elif prefix == "T":
        event_data = add_identity_task_result(db, camera, data, task_id)
        if event_data:
            on_event(event_data)
    else:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "error": None}


@router.post("/faceRecognition")
async def face_recognition(
    face_recognition_data: FaceRecognitionRequestSchema,
    db: Session = Depends(get_pg_db),
    mongo_db=Depends(get_mongo_db),
    minio_client=Depends(get_minio_client),
):
    """
    data = {
        'request_type': 'faceRecognition',
        'IP': '192.168.31.64',
        'device_ip': '192.168.31.64',
        'device_id': 'H010001172B0100010772',
        'timestamp': 1706961512,
        'snap_time': 1706961512,
        'snap_time_ms': 1706961512503,
        'frpic_name': 'FACE_0_20240203195832503_13.jpg',
        'user_list': 0,
        'mask': 0,
        'user_name': None,
        'idcard_number': None,
        'user_id': None,
        'access_card': None,
        'group': None,
        'comp_score': None,
        'sex': None,
        'channel': 0,
        'image': '/9j/4AAQSkZJRgABAQIAdgB2AAD/7wAPAAAAAAAAAAAAAAAAAP/9OtCQcl+p//2Q==',
        'fullview_image': '/9j/4AAQSkZJRgABAQIAdgB2AAD/7wAPAAAAAAAAAAAAAAAAAP/9OtCQcl+p//2Q==',
        'body_image': '/9j/4AAQSkZJRgABAQIAdgB2AAD/7wAPAAAAAAAAAAAAAAAAAP/9OtCQcl+p//2Q==',
        'face_yaw': 0,
        'face_pitch': -8,
        'face_roll': -1,
        'face_id': 13,
        'face_quality': 9646,
        'eva_age': 0,
        'eva_coatstyle': 0,
        'eva_pans': 0,
        'eva_bag': 0,
        'eva_rxstaus': 0,
        'eva_hair': 0,
        'car_label': 0,
        'car_type': 0,
        'car_color': 0
    }
    """

    smart_camera = db.query(SmartCamera).filter_by(device_id=face_recognition_data.device_id, is_active=True).first()
    if not smart_camera:
        return {"message": f"Smart camera with device id {face_recognition_data.device_id} not found"}

    if face_recognition_data.user_id is None:
        file_name = f"{face_recognition_data.device_id}/{uuid.uuid4()}.jpg"
    else:
        file_name = f"{face_recognition_data.device_id}/{face_recognition_data.user_id}/{uuid.uuid4()}.jpg"

    image_data = base64.b64decode(face_recognition_data.image)
    image_file = io.BytesIO(image_data)
    acl = "public-read"

    background_image = face_recognition_data.fullview_image or None
    background_image_data = base64.b64decode(background_image) if background_image else None
    background_image_file = io.BytesIO(background_image_data) if background_image_data else None
    body_image = face_recognition_data.body_image or None
    body_image_data = base64.b64decode(body_image) if body_image else None
    body_image_file = io.BytesIO(body_image_data) if body_image_data else None

    image_url = None
    capture_type = None

    if smart_camera.type == "enter":
        face_recognition_data.event_type = "enter"
        attendance_type = "enter"
    elif smart_camera.type == "exit":
        face_recognition_data.event_type = "exit"
        attendance_type = "exit"
    else:
        face_recognition_data.event_type = "unknown"
        attendance_type = "unknown"

    capture_time = datetime.now()
    visitor = None
    identity = None
    wanted = None
    relative = None
    if face_recognition_data.user_id:
        if face_recognition_data.user_list == 2:
            if face_recognition_data.user_id[0] == "v":
                face_recognition_data.user_id = int(face_recognition_data.user_id[1:])
                visitor = db.query(Visitor).filter_by(id=face_recognition_data.user_id, is_active=True).first()
            elif face_recognition_data.user_id[0] == "r":
                face_recognition_data.user_id = int(face_recognition_data.user_id[1:])
                relative = db.query(Relative).filter_by(id=face_recognition_data.user_id, is_active=True).first()
            else:
                face_recognition_data.user_id = int(face_recognition_data.user_id)
                identity = (
                    db.query(Identity)
                    .filter_by(id=face_recognition_data.user_id, tenant_entity_id=smart_camera.tenant_entity_id)
                    .first()
                )
        elif face_recognition_data.user_list == 1 and face_recognition_data.user_id[0] == "w":
            face_recognition_data.user_id = int(face_recognition_data.user_id[1:])
            wanted = db.query(Wanted).filter_by(id=face_recognition_data.user_id, is_active=True).first()

    tenant_entity = db.query(TenantEntity).filter_by(id=smart_camera.tenant_entity_id, is_active=True).first()
    room = db.query(Room).filter_by(id=smart_camera.room_id, is_active=True).first()
    district = db.query(District).filter_by(id=tenant_entity.district_id, is_active=True).first()
    district_name = district.name if district else None

    background_image_url, body_image_url = None, None
    if face_recognition_data.user_list == 0:
        face_recognition_data.user_name = "Unknown"
        capture_type = "visitor"
        minio_client.put_object(
            BUCKET_VISITOR,
            file_name,
            image_file,
            len(image_data),
            content_type="image/jpeg",
            metadata={"x-amz-acl": acl},
        )
        image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_VISITOR}/{file_name}"
        if background_image_file:
            minio_client.put_object(
                BUCKET_VISITOR_BACKGROUND,
                file_name,
                background_image_file,
                len(background_image_data),
                content_type="image/jpeg",
                metadata={"x-amz-acl": acl},
            )
            background_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_VISITOR_BACKGROUND}/{file_name}"
        if body_image_file:
            minio_client.put_object(
                BUCKET_VISITOR_BODY,
                file_name,
                body_image_file,
                len(body_image_data),
                content_type="image/jpeg",
                metadata={"x-amz-acl": acl},
            )
            body_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_VISITOR_BODY}/{file_name}"
        if tenant_entity.trackable:
            visitor = Visitor(
                photo=image_url,
                smart_camera_id=int(str(smart_camera.id)),
                tenant_entity_id=int(str(smart_camera.tenant_entity_id)),
            )
            db.add(visitor)
            db.commit()
            db.refresh(visitor)
            create_task_to_scamera(db, "add_visitor", smart_camera.id, visitor.id, "visitor")
        attendance_data = {
            "smart_camera_id": smart_camera.id,
            "attendance_type": attendance_type,
            "attendance_datetime": capture_time,
            "snapshot_url": image_url,
            "background_image_url": background_image_url,
            "body_image_url": body_image_url,
            "visitor_id": visitor.id if visitor else None,
        }
        visitor_attendance = VisitorAttendance(**attendance_data)
        db.add(visitor_attendance)
        db.commit()
        db.refresh(visitor_attendance)

        send_attendance_to_websocket.delay(
            attendance_id=visitor_attendance.id, tenant_entity_id=None, attendance_category="visitor"
        )

        data = {
            "id": visitor_attendance.id,
            "user_type": "visitor",
            "user_group": None,
            "pinfl": None,
            "snapshot_url": image_url,
            "background_image_url": background_image_url,
            "body_image_url": body_image_url,
            "event_type": attendance_type,
            "capture_datetime": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
            "capture_timestamp": int(capture_time.timestamp()),
            "comp_score": None,
            "device_lat": smart_camera.device_lat,
            "device_long": smart_camera.device_long,
            "tenant_entity_id": smart_camera.tenant_entity_id,
            "building_id": room.building_id,
            "address": tenant_entity.name if tenant_entity else None,
            "camera_name": smart_camera.name,
            "district": district_name,
        }
        integration = (
            db.query(Integrations).filter_by(tenant_id=smart_camera.tenant_id, module_id=1, is_active=True).first()
        )
        if integration:
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
        third_integrations = (
            db.query(ThirdPartyIntegration)
            .join(
                ThirdPartyIntegrationTenant,
                ThirdPartyIntegration.id == ThirdPartyIntegrationTenant.third_party_integration_id,
            )
            .filter(
                and_(ThirdPartyIntegrationTenant.tenant_id == smart_camera.tenant_id, ThirdPartyIntegration.is_active)
            )
            .all()
        )
        for integration3 in third_integrations:
            notify_integrator.delay(
                module_id=1,
                module_name="Face Attendance",
                data=data,
                callback_url=integration3.api,
                auth_type=integration3.auth_type,
                username=integration3.api_username,
                password=integration3.api_password,
                token=integration3.api_token,
                token_type=integration3.api_token_type,
            )
        visitor_analytics = mongo_db["visitor_analytics"]
        visitor_analytics.insert_one(
            {
                "device_id": face_recognition_data.device_id,
                "device_ip": face_recognition_data.device_ip,
                "timestamp": face_recognition_data.timestamp,
                "capture_time": capture_time,
                "snap_time": face_recognition_data.snap_time,
                "username": face_recognition_data.user_name,
                "user_id": face_recognition_data.user_id,
                "sex": face_recognition_data.eva_sex,
                "age": face_recognition_data.eva_age,
                "face_id": face_recognition_data.face_id,
                "image": image_url,
            }
        )

    elif face_recognition_data.user_list == 2:
        if visitor:
            capture_type = "visitor"
            minio_client.put_object(
                BUCKET_VISITOR,
                file_name,
                image_file,
                len(image_data),
                content_type="image/jpeg",
                metadata={"x-amz-acl": acl},
            )
            image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_VISITOR}/{file_name}"
            if background_image_file:
                minio_client.put_object(
                    BUCKET_VISITOR_BACKGROUND,
                    file_name,
                    background_image_file,
                    len(background_image_data),
                    content_type="image/jpeg",
                    metadata={"x-amz-acl": acl},
                )
                background_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_VISITOR_BACKGROUND}/{file_name}"
            if body_image_file:
                minio_client.put_object(
                    BUCKET_VISITOR_BODY,
                    file_name,
                    body_image_file,
                    len(body_image_data),
                    content_type="image/jpeg",
                    metadata={"x-amz-acl": acl},
                )
                body_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_VISITOR_BODY}/{file_name}"
            attendance_data = {
                "smart_camera_id": smart_camera.id,
                "attendance_type": attendance_type,
                "attendance_datetime": capture_time,
                "snapshot_url": image_url,
                "background_image_url": background_image_url,
                "body_image_url": body_image_url,
                "visitor_id": visitor.id if visitor else None,
            }
            visitor_attendance = VisitorAttendance(**attendance_data)
            db.add(visitor_attendance)
            db.commit()
            db.refresh(visitor_attendance)

            send_attendance_to_websocket.delay(
                attendance_id=visitor_attendance.id, tenant_entity_id=None, attendance_category="visitor"
            )

            integration = (
                db.query(Integrations).filter_by(tenant_id=smart_camera.tenant_id, module_id=1, is_active=True).first()
            )
            if integration:
                data = {
                    "id": visitor_attendance.id,
                    "user_type": "visitor",
                    "user_group": 1,
                    "pinfl": None,
                    "snapshot_url": image_url,
                    "background_image_url": background_image_url,
                    "body_image_url": body_image_url,
                    "event_type": attendance_type,
                    "capture_datetime": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "capture_timestamp": int(capture_time.timestamp()),
                    "comp_score": face_recognition_data.comp_score or 0.0,
                    "device_lat": smart_camera.device_lat,
                    "device_long": smart_camera.device_long,
                    "tenant_entity_id": smart_camera.tenant_entity_id,
                    "building_id": room.building_id,
                    "address": tenant_entity.name if tenant_entity else None,
                    "camera_name": smart_camera.name,
                    "district": district_name,
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
        if identity:
            capture_type = "identity"
            minio_client.put_object(
                BUCKET_IDENTITY_ATTENDANCE,
                file_name,
                image_file,
                len(image_data),
                content_type="image/jpeg",
                metadata={"x-amz-acl": acl},
            )
            image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_IDENTITY_ATTENDANCE}/{file_name}"
            if background_image_file:
                minio_client.put_object(
                    BUCKET_IDENTITY_BACKGROUND,
                    file_name,
                    background_image_file,
                    len(background_image_data),
                    content_type="image/jpeg",
                    metadata={"x-amz-acl": acl},
                )
                background_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_IDENTITY_BACKGROUND}/{file_name}"
            if body_image_file:
                minio_client.put_object(
                    BUCKET_IDENTITY_BODY,
                    file_name,
                    body_image_file,
                    len(body_image_data),
                    content_type="image/jpeg",
                    metadata={"x-amz-acl": acl},
                )
                body_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_IDENTITY_BODY}/{file_name}"
            data = {
                "attendance_type": attendance_type,
                "attendance_datetime": capture_time,
                "snapshot_url": image_url,
                "background_image_url": background_image_url,
                "body_image_url": body_image_url,
                "identity_id": identity.id,
                "tenant_id": identity.tenant_id,
                "tenant_entity_id": identity.tenant_entity_id,
                "smart_camera_id": smart_camera.id,
                "comp_score": face_recognition_data.comp_score or 0.0,
                "lat": smart_camera.device_lat,
                "lon": smart_camera.device_long,
                "bucket_name": BUCKET_IDENTITY_ATTENDANCE,
                "object_name": file_name,
            }
            identity_attendance = Attendance(**data)
            db.add(identity_attendance)
            db.commit()
            db.refresh(identity_attendance)

            send_attendance_to_websocket.delay(
                attendance_id=identity_attendance.id,
                tenant_entity_id=identity_attendance.tenant_entity_id,
                attendance_category="usual",
            )

            integration = (
                db.query(Integrations).filter_by(tenant_id=identity.tenant_id, module_id=1, is_active=True).first()
            )
            if integration:
                data = {
                    "id": identity.id,
                    "user_type": "identity",
                    "user_group": identity.identity_group,
                    "identity_type": identity.identity_type,
                    "external_id": identity.external_id,
                    "mtt_id": tenant_entity.external_id,
                    "tenant_id": identity.tenant_id,
                    "pinfl": identity.pinfl,
                    "snapshot_url": image_url,
                    "background_image_url": background_image_url,
                    "body_image_url": body_image_url,
                    "event_type": attendance_type,
                    "capture_datetime": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "capture_timestamp": int(capture_time.timestamp()),
                    "comp_score": face_recognition_data.comp_score or 0.0,
                    "device_lat": smart_camera.device_lat,
                    "device_long": smart_camera.device_long,
                    "by_mobile": False,
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
        if relative:
            capture_type = "relative"
            minio_client.put_object(
                BUCKET_RELATIVE_ATTENDANCE,
                file_name,
                image_file,
                len(image_data),
                content_type="image/jpeg",
                metadata={"x-amz-acl": acl},
            )
            image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_RELATIVE_ATTENDANCE}/{file_name}"
            data = {
                "attendance_type": attendance_type,
                "attendance_datetime": capture_time,
                "snapshot_url": image_url,
                "relative_id": relative.id,
                "smart_camera_id": smart_camera.id,
                "comp_score": face_recognition_data.comp_score or 0.0,
                "tenant_id": smart_camera.tenant_id,
            }
            relative_attendance = RelativeAttendance(**data)
            db.add(relative_attendance)
            db.commit()
            db.refresh(relative_attendance)

            send_attendance_to_websocket.delay(
                attendance_id=relative_attendance.id, tenant_entity_id=None, attendance_category="relative-visitor"
            )

            kid_identities = get_relative_identities(db, relative.id)
            if kid_identities:
                identity_ids = [int(item.identity_id) for item in kid_identities]
                try:
                    async with websockets.connect(
                        f"ws://0.0.0.0:8008/customer/identity/ws/parent/{smart_camera.tenant_entity_id}"
                    ) as websocket:
                        dict_relative = {
                            "relative": {
                                "id": relative.id,
                                "first_name": relative.first_name,
                                "last_name": relative.last_name,
                                "photo": relative.photo,
                                "email": relative.email,
                                "phone": relative.phone,
                                "pinfl": relative.pinfl,
                                "external_id": relative.external_id,
                            },
                            "snapshot_url": image_url,
                            "date": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
                            "identity_ids": identity_ids,
                        }
                        await websocket.send(json.dumps(dict_relative))
                except Exception as e:
                    logger.info(f"WEBSOCKET SEND PARENT ERROR: {e}")
    elif face_recognition_data.user_list == 1:
        logger.info(
            f"PROCESSING WANTEDS: USER_LIST {face_recognition_data.user_list}, "
            f"USER_ID: {face_recognition_data.user_id}, device_id: {smart_camera.device_id}"
        )
        capture_type = "wanted"
        minio_client.put_object(
            WANTED_BUCKET,
            file_name,
            image_file,
            len(image_data),
            content_type="image/jpeg",
            metadata={"x-amz-acl": acl},
        )
        image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{WANTED_BUCKET}/{file_name}"
        if wanted:
            if background_image_file:
                minio_client.put_object(
                    BUCKET_WANTED_BACKGROUND,
                    file_name,
                    background_image_file,
                    len(background_image_data),
                    content_type="image/jpeg",
                    metadata={"x-amz-acl": acl},
                )
                background_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_WANTED_BACKGROUND}/{file_name}"
            if body_image_file:
                minio_client.put_object(
                    BUCKET_WANTED_BODY,
                    file_name,
                    body_image_file,
                    len(body_image_data),
                    content_type="image/jpeg",
                    metadata={"x-amz-acl": acl},
                )
                body_image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_WANTED_BODY}/{file_name}"
            attendance_data = {
                "attendance_type": attendance_type,
                "attendance_datetime": capture_time,
                "snapshot_url": image_url,
                "background_image_url": background_image_url,
                "body_image_url": body_image_url,
                "wanted_id": wanted.id,
                "tenant_id": smart_camera.tenant_id,
                "smart_camera_id": smart_camera.id,
                "comp_score": face_recognition_data.comp_score or 0.0,
            }
            wanted_attendance = WantedAttendance(**attendance_data)
            db.add(wanted_attendance)
            db.commit()
            db.refresh(wanted_attendance)

            send_attendance_to_websocket.delay(
                attendance_id=wanted_attendance.id, tenant_entity_id=None, attendance_category="wanted"
            )

            data = {
                "id": wanted.id,
                "user_type": "wanted",
                "user_group": None,
                "pinfl": wanted.pinfl,
                "snapshot_url": image_url,
                "background_image_url": background_image_url,
                "body_image_url": body_image_url,
                "event_type": attendance_type,
                "capture_datetime": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
                "capture_timestamp": int(capture_time.timestamp()),
                "comp_score": face_recognition_data.comp_score or 0.0,
                "device_lat": smart_camera.device_lat,
                "device_long": smart_camera.device_long,
                "main_photo": wanted.photo,
                "first_name": wanted.first_name,
                "last_name": wanted.last_name,
                "accusation": wanted.accusation,
                "tenant_entity_id": wanted.tenant_entity_id,
                "address": tenant_entity.name if tenant_entity else None,
                "camera_name": smart_camera.name,
                "district": district_name,
                "description": wanted.description,
                "concern_level": wanted.concern_level,
                "phone": wanted.phone,
                "room_id": smart_camera.room_id,
                "room_name": room.name,
                "room_description": room.description,
                "building_id": room.building_id,
            }
            integration = (
                db.query(Integrations).filter_by(tenant_id=smart_camera.tenant_id, module_id=1, is_active=True).first()
            )
            if integration:
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
            third_integrations = (
                db.query(ThirdPartyIntegration)
                .join(
                    ThirdPartyIntegrationTenant,
                    ThirdPartyIntegration.id == ThirdPartyIntegrationTenant.third_party_integration_id,
                )
                .filter(
                    and_(
                        ThirdPartyIntegrationTenant.tenant_id == smart_camera.tenant_id, ThirdPartyIntegration.is_active
                    )
                )
                .all()
            )
            for integration3 in third_integrations:
                notify_integrator.delay(
                    module_id=1,
                    module_name="Face Attendance",
                    data=data,
                    callback_url=integration3.api,
                    auth_type=integration3.auth_type,
                    username=integration3.api_username,
                    password=integration3.api_password,
                    token=integration3.api_token,
                    token_type=integration3.api_token_type,
                )
    else:
        logger.error(f"Unknown user_list: {face_recognition_data.user_list}")
    try:
        async with websockets.connect(f"ws://{WEBSOCKET_URL}/ws/{smart_camera.id}") as websocket:
            dict_capture = {
                "id": face_recognition_data.user_id,
                "user_name": face_recognition_data.user_name,
                "snapshot_url": image_url,
                "background_image_url": background_image_url,
                "body_image_url": body_image_url,
                "capture_type": capture_type,
                "first_name": face_recognition_data.user_name,
                "last_name": "",
                "gender": face_recognition_data.eva_sex,
                "age": face_recognition_data.eva_age,
                "age_interval": face_recognition_data.eva_age,
                "is_counted": 0,
                "created_at": capture_time.strftime("%Y-%m-%d %H:%M:%S"),
                "count_type": 0,
            }
            await websocket.send(json.dumps(dict_capture))
    except Exception as e:
        logger.error(f"WEBSOCKET ERROR: {str(e)}")
    return {"message": "Face recognition processed successfully."}
