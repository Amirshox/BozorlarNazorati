import base64
import gc
import io
import json
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

import PIL.Image
import requests
import sentry_sdk
import tritonclient.grpc as grpcclient
from celery import Celery, Task, group, signals
from celery.exceptions import TaskError
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
from celery_batches import Batches
from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from minio import Minio, S3Error
from pymongo import MongoClient
from requests import RequestException
from requests.auth import HTTPBasicAuth
from sqlalchemy import and_, func, update
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.session import Session

from database import db_identity_smart_camera
from database.database import (
    SessionLocal,
    get_cron_celery_mongo_db,
    get_identity_celery_mongo_db,
    get_rabbitmq_sync_connection,
)
from database.db_relative import create_relative, get_relative
from database.db_smartcamera import create_task_to_scamera
from database.minio_client import get_minio_client, get_minio_ssd_client
from models import (
    Attendance,
    AttendanceAntiSpoofing,
    BazaarSmartCameraSnapshot,
    ErrorSmartCamera,
    Identity,
    IdentityRelative,
    IdentitySmartCamera,
    Integrations,
    SmartCamera,
    TenantEntity,
    Visitor,
    WantedSmartCamera,
)
from models.identity import Package, RelativeSmartCamera
from schemas.identity import RelativeBase
from utils.image_processing import (
    MINIO_HOST,
    MINIO_PROTOCOL,
    check_image_HD,
    get_image_from_query,
    get_image_from_url,
    get_main_error_text,
    image_url_to_base64,
    make_minio_url_from_image,
    pre_process_image,
)
from utils.kindergarten import BASIC_AUTH, NODAVLAT_BASE_URL, get_user_photo_by_pinfl

rabbit_connection = None

app = Celery(
    "tasks",
    broker=os.getenv("REDIS_URL", "redis://localhost:6378/0"),
    # backend=os.getenv("MONGODB_URL", "mongodb://root:example@localhost:27018"),
)


@signals.celeryd_init.connect
def init_sentry(**_kwargs):
    sentry_sdk.init(
        dsn="https://e987eccd12abfbaea4cbf6beb980435e@sentry.platon.uz/10",
        traces_sample_rate=1.0,
    )


app.conf.beat_schedule = {
    "run-every-three-hour": {"task": "tasks.disable_all_rtmp_scameras", "schedule": crontab(minute="0", hour="*/3")},
    "delete-visitors-from-scamera": {
        "task": "tasks.delete_visitors_from_scamera",
        "schedule": crontab(minute="0", hour="0"),
    },
    "quarter-task-8-to-8": {
        "task": "tasks.get_camera_snapshots",
        "schedule": crontab(minute="0,15,30,45", hour="8-19"),
    },
    "hourly-task-8-to-6": {
        "task": "tasks.refresh_payment_status",
        "schedule": crontab(minute="0", hour="8-17"),
    },
    "daily-task-sync-attendance-to-platon": {
        "task": "tasks.send_attendance_leftovers_to_platon_beat_task",
        "schedule": crontab(minute="0", hour="21"),
    },
}
app.conf.timezone = "Asia/Tashkent"

IDENTITY_BUCKET = os.getenv("MINIO_BUCKET_IDENTITY", "identity")
MINIO_CLEAR_SPOOF = os.getenv("MINIO_CLEAR_SPOOF", "clear-attendance")
MINIO_COMPROMISED_SPOOF = os.getenv("MINIO_COMPROMISED_SPOOF", "compromised-attendance")
BUCKET_IDENTITY_ATTENDANCE = os.getenv("BUCKET_IDENTITY_ATTENDANCE", "identity-attendance")
RELATIVE_IDENTITY_BUCKET = os.getenv("MINIO_RELATIVE_IDENTITY", "relative-identity")

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")

BAZAAR_TENANT_ID = 19
SNAPSHOT_BAZAAR_SCAMERA_BUCKET = os.getenv("SNAPSHOT_BAZAAR_SCAMERA_BUCKET", "bazaar-camera")
BAZAAR_CALLBACK_URL = "http://10.3.7.131:8009/3rdparty/roi_analytics"
BAZAAR_PAYMENT_STATUS_URL = "http://10.3.7.131:8009/3rdparty/update_payment_status"

batch_attendance_basic_auth = {"Authorization": "Basic cmVhbHNvZnRhaTpyZWFsc29mdGFpNDU2NSE="}

logger = logging.getLogger(__name__)

gc.enable()
minio_client: Minio = get_minio_client()
minio_ssd_client: Minio = get_minio_ssd_client()
mongo_client = None
triton_client = None

if not get_minio_client().bucket_exists(RELATIVE_IDENTITY_BUCKET):
    get_minio_client().make_bucket(RELATIVE_IDENTITY_BUCKET)
if not get_minio_client().bucket_exists(MINIO_CLEAR_SPOOF):
    get_minio_client().make_bucket(MINIO_CLEAR_SPOOF)
if not get_minio_client().bucket_exists(MINIO_COMPROMISED_SPOOF):
    get_minio_client().make_bucket(MINIO_COMPROMISED_SPOOF)
if not get_minio_client().bucket_exists(BUCKET_IDENTITY_ATTENDANCE):
    get_minio_client().make_bucket(BUCKET_IDENTITY_ATTENDANCE)


def is_retry(response: requests.Response) -> bool:
    return response.status_code in [404, 408] or "Unknown" in response.text


def on_event(data: dict):
    callback_url = data["callback_url"]
    auth = data["auth"]
    payload = data["payload"]

    if callback_url and payload:
        db = get_identity_celery_mongo_db()
        post = {"task_id": data["message_id"], "data": payload, "created_at": datetime.now()}
        db["identity_callback"].insert_one(post)
        try:
            if not auth:
                response = requests.post(callback_url, json=payload)
                response.raise_for_status()
            elif auth.get("auth").lower() == "basic":
                basic_auth = HTTPBasicAuth(auth.get("username"), auth.get("password"))
                response = requests.post(callback_url, json=payload, auth=basic_auth)
                response.raise_for_status()
            elif auth.get("auth").lower() == "jwt":
                response = requests.post(
                    callback_url,
                    json=payload,
                    headers={"Authorization": f"{auth.get('token_type')} {auth.get('token')}"},
                )
                response.raise_for_status()
            return True
        except requests.RequestException as e:
            return str(e)
    return "Callback url or payload missing"


class DatabaseTask(Task):
    _db_session: Session = None

    def after_return(self, *args, **kwargs):
        print("Closing db session")
        if self._db_session:
            self._db_session.close()
            print("Closed db session")
            self._db_session = None

    def get_db(self) -> Session:
        print("Getting db session")
        if not self._db_session:
            self._db_session = SessionLocal()
            print("Creating new db session")
        print("Returning db session")
        return self._db_session


class EventDrivenTask(Task):
    abstract = True

    def on_success(self, retval, task_id, args, kwargs):
        callback_url = retval.get("callback_url")
        auth = retval.get("auth")
        payload = retval.get("payload")
        if not callback_url:
            return {"success": False, "message": "Callback Url not found"}
        message = None
        try:
            if not auth:
                response = requests.post(callback_url, json=payload)
                message = response.text
                response.raise_for_status()
            elif auth.get("auth").lower() == "basic":
                basic_auth = HTTPBasicAuth(auth.get("username"), auth.get("password"))
                response = requests.post(callback_url, json=payload, auth=basic_auth)
                message = response.text
                response.raise_for_status()
            elif auth.get("auth").lower() == "jwt":
                response = requests.post(
                    callback_url,
                    json=payload,
                    headers={"Authorization": f"{auth.get('token_type')} {auth.get('token')}"},
                )
                message = response.text
                response.raise_for_status()
            return {"success": True, "message": f"Task {task_id} succeeded with result: {retval}"}
        except requests.exceptions.MissingSchema as e:
            logger.info(f"notify1: missing: error: {e}, msg: {message}, callback_url: {callback_url}")
            return {"success": False, "message": "Invalid URL"}
        except requests.exceptions.HTTPError as exc:
            logger.info(f"notify1: HTTPError: {exc}, msg: {message}")
            self.retry(exc=exc, countdown=3600, max_retries=10)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        callback_url = kwargs.get("callback_url")
        payload = kwargs.get("payload")
        auth = kwargs.get("auth")
        if not callback_url:
            return {"success": False, "message": "Callback Url not found"}
        message = None
        try:
            if not auth:
                response = requests.post(callback_url, json=payload)
                message = response.text
                response.raise_for_status()
            elif auth.get("auth").lower() == "basic":
                basic_auth = HTTPBasicAuth(auth.get("username"), auth.get("password"))
                response = requests.post(callback_url, json=payload, auth=basic_auth)
                message = response.text
                response.raise_for_status()
            elif auth.get("auth").lower() == "jwt":
                response = requests.post(
                    callback_url,
                    json=payload,
                    headers={"Authorization": f"{auth.get('token_type')} {auth.get('token')}"},
                )
                message = response.text
                response.raise_for_status()
            return {"success": False, "message": f"Task {task_id} failed with exc: {exc}"}
        except requests.RequestException as e:
            logger.info(f"notify2: error: {e}, callback_url: {callback_url}, msg: {message}")
        except Exception as e:
            logger.info(f"notify2: error: {e}, callback_url: {callback_url}, msg: {message}")


# @app.task
# def log_entry_task(log_entry):
#     client = MongoClient(MONGO_DB_URL, maxPoolSize=50)
#     db = client["one-system"]
#     collection = db["http_logs"]
#
#     with contextlib.suppress(DocumentTooLarge):
#         collection.insert_one(log_entry)


@app.task(bind=True, base=DatabaseTask)
def disable_all_rtmp_scameras(self):
    db = self.get_db()
    scameras = db.query(SmartCamera).filter_by(is_active=True).all()
    errors = []
    for smart_camera in scameras:
        url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setRtmpConf"
        payload_dict = {
            "password": smart_camera.password,
            "channel": 0,
            "RtmpEnable": 0,
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
            if response.json()["code"] != 0:
                error_response = {"id": smart_camera.id, "error": get_main_error_text(response)}
                errors.append(error_response)
        except Exception as e:
            error_response = {"id": smart_camera.id, "error": str(e)}
            errors.append(error_response)
    db_mongo = get_cron_celery_mongo_db()
    post = {"task_id": self.request.id, "errors": errors, "created_at": datetime.now()}
    db_mongo["cron"].insert_one(post)
    return {"success": True, "message": f"Cron task {self.request.id} succeeded"}


def make_inference_request(snapshot_id):
    requests.get(
        url=BAZAAR_CALLBACK_URL + f"?snapshot_id={snapshot_id}",
        headers={"Content-Type": "application/json"},
    )


@app.task(bind=True)
def refresh_payment_status():
    requests.put(BAZAAR_PAYMENT_STATUS_URL)


@app.task(bind=True, base=DatabaseTask)
def get_camera_snapshots(self):
    db: Session = self.get_db()

    smart_cameras = db.query(SmartCamera).filter(SmartCamera.tenant_id == BAZAAR_TENANT_ID, SmartCamera.is_active).all()

    for each_smart_camera in smart_cameras:
        url = f"http://{CAMERA_MANAGER_URL}/device/{each_smart_camera.device_id}/equipment/getFmtSnap"
        payload_dict = {"password": each_smart_camera.password, "fmt": 0}
        payload = json.dumps(payload_dict)

        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
            timeout=10,
        )

        if response.status_code != 200 or response.json()["code"] != 0:
            return None

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
            smart_camera_id=each_smart_camera.id, snapshot_url=photo_url, tenant_id=each_smart_camera.tenant_id
        )

        db.add(new_snapshot)
        db.commit()
        db.refresh(new_snapshot)

        make_inference_request(new_snapshot.id)

        # request_thread = threading.Thread(target=lambda: make_inference_request(new_snapshot.id))  # noqa

        # request_thread = threading.Thread(target=make_inference_request, args=(new_snapshot.id))

        # request_thread.daemon = True

        # request_thread.start()


@app.task(bind=True, base=DatabaseTask)
def delete_visitors_from_scamera(self):
    db = self.get_db()
    trackable_entity_ids = db.query(TenantEntity.id).filter_by(trackable=True, is_active=True).all()
    for tenant_entity in trackable_entity_ids:
        smart_camera_ids = db.query(SmartCamera.id).filter_by(tenant_entity_id=tenant_entity.id, is_active=True).all()
        for smart_camera in smart_camera_ids:
            visitor_ids = (
                db.query(Visitor.id)
                .filter_by(smart_camera_id=smart_camera.id, tenant_entity_id=tenant_entity.id, is_active=True)
                .all()
            )
            for visitor in visitor_ids:
                create_task_to_scamera(db, "delete_visitor", smart_camera.id, visitor.id, "visitor")
    return {"success": True, "message": f"Cron task {self.request.id} succeeded"}


@app.task(bind=True, base=DatabaseTask)
def add_identity_by_task(self, tenant_entity_id: int, smart_camera_id: int):
    db = self.get_db()
    identities = db_identity_smart_camera.get_unload_identities(db, tenant_entity_id, smart_camera_id).all()
    for identity in identities:
        try:
            is_HD_image = check_image_HD(identity.photo)
        except Exception as e:
            print(f"Image is not HD: {identity.photo}, {e}")
            is_HD_image = False
        if is_HD_image:
            create_task_to_scamera(db, "add", smart_camera_id, identity.id, "identity")
        else:
            print(f"Image is not HD: {identity.photo}")
    return True


# @app.task(bind=True, base=DatabaseTask)
# def sync_with_platon_task(self, tenant_entity_id: int, tenant_id: int, data: list, identity_group: int | None = None):
#     def check_item(_id: int, data_list: list, ex_id: Optional[str] = None) -> bool:
#         return any(_id == list_item["id"] or (ex_id and ex_id == list_item["external_id"]) for list_item in data_list)
#
#     db = self.get_db()
#     minio_client = get_minio_client()
#     identities = (
#         db.query(Identity)
#         .filter_by(tenant_entity_id=tenant_entity_id, identity_group=identity_group, is_active=True)
#         .all()
#     )
#     for identity in identities:
#         if not check_item(identity.id, data, identity.external_id):
#             identity.is_active = False
#             db.commit()
#             db.refresh(identity)
#     for item in data:
#         if item["id"]:
#             identity = (
#                 db.query(Identity).filter_by(id=item["id"], tenant_entity_id=tenant_entity_id, is_active=True).first()
#             )
#         else:
#             identity = (
#                 db.query(Identity)
#                 .filter_by(
#                     tenant_entity_id=tenant_entity_id,
#                     identity_type=item["identity_type"],
#                     identity_group=identity_group,
#                     external_id=item["external_id"],
#                     is_active=True,
#                 )
#                 .first()
#             )
#         if identity:
#             if item["photo"] and (
#                 item["photo"] != identity.recieved_photo_url or not item["photo"].startswith("https://s3.realsoft.ai")
#             ):
#                 main_image = get_image_from_query(item["photo"])
#                 main_photo_url = make_minio_url_from_image(
#                     minio_client, main_image, IDENTITY_BUCKET, item["pinfl"], is_check_hd=False
#                 )
#                 item["photo"] = main_photo_url
#             if item["first_name"] and item["first_name"] != identity.first_name:
#                 identity.first_name = item["first_name"]
#             if item["last_name"]:
#                 identity.last_name = item["last_name"]
#             if item["photo"]:
#                 identity.photo = item["photo"]
#             if item["pinfl"]:
#                 identity.pinfl = item["pinfl"]
#             if item["identity_group"]:
#                 identity.identity_group = item["identity_group"]
#             if item["identity_type"]:
#                 identity.identity_type = item["identity_type"]
#             if item["external_id"]:
#                 identity.external_id = item["external_id"]
#             if item["group_id"]:
#                 identity.group_id = item["group_id"]
#             if item["group_name"]:
#                 identity.group_name = item["group_name"]
#             bucket_name, object_name = extract_minio_url(url=item["photo"]) if item["photo"] else (None, None)
#             identity.bucket_name = bucket_name
#             identity.object_name = object_name
#             identity.version += 1
#             db.commit()
#             db.refresh(identity)
#         else:
#             recieved_photo_url = None
#             if item["photo"]:
#                 try:
#                     recieved_photo_url = item["photo"] if is_image_url(item["photo"]) else None
#                     main_image = get_image_from_query(item["photo"])
#                     main_photo_url = make_minio_url_from_image(
#                         minio_client, main_image, IDENTITY_BUCKET, item["pinfl"], is_check_hd=False
#                     )
#                     item["photo"] = main_photo_url
#                 except Exception:
#                     item["photo"] = None
#             new_item = IdentityCreate(
#                 first_name=item["first_name"],
#                 last_name=item["last_name"],
#                 photo=item["photo"],
#                 email=item["email"],
#                 phone=item["phone"],
#                 pinfl=item["pinfl"],
#                 identity_group=item["identity_group"],
#                 identity_type=item["identity_type"],
#                 external_id=item["external_id"],
#                 group_id=item["group_id"],
#                 group_name=item["group_name"],
#                 tenant_entity_id=tenant_entity_id,
#             )
#             try:
#                 create_identity(db, tenant_id, new_item, recieved_photo_url)
#             except Exception as e:
#                 logger.info(f"create identity failed with task sync_with_platon_task: {e}")


# @app.task(bind=True, base=DatabaseTask)
# def create_identity_list_task(self, smart_camera_id: int, data: list):
#     db = self.get_db()
#     smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
#     for item in data:
#         new_item = IdentityCreate(
#             first_name=item["first_name"],
#             last_name=item["last_name"],
#             photo=item["photo"],
#             email=item["email"],
#             phone=item["phone"],
#             pinfl=item["pinfl"],
#             identity_group=item["identity_group"],
#             identity_type=item["identity_type"],
#             left_side_photo=item["left_side_photo"],
#             right_side_photo=item["right_side_photo"],
#             top_side_photo=item["top_side_photo"],
#             embedding=item["embedding"],
#             cropped_image=item["cropped_image"],
#             embedding512=item["embedding512"],
#             cropped_image512=item["cropped_image512"],
#             external_id=item["external_id"],
#             group_id=item["group_id"],
#             group_name=item["group_name"],
#             tenant_entity_id=item["tenant_entity_id"],
#         )
#         try:
#             create_identity(db, smart_camera.tenant_id, new_item, item["recieved_photo_url"])
#         except Exception as e:
#             logger.info(f"create identity failed with task create_identity_list_task: {e}")


@app.task(bind=True, base=EventDrivenTask, max_retries=10)
def notify_integrator(
        self,
        module_id: int,
        module_name: str,
        data: dict,
        callback_url: str,
        auth_type: Optional[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
        token_type: Optional[str] = None,
):
    message_id = self.request.id  # Task ID
    payload = {"message_id": message_id, "module_id": module_id, "module_name": module_name, "data": data}

    if not auth_type:
        auth = None
    elif auth_type.lower() in ["basic", "jwt"] and username and password:
        auth = {"auth": auth_type, "username": username, "password": password}
    elif token:
        auth = {"auth": auth_type, "token": token, "token_type": token_type}
    else:
        auth = None

    return {"payload": payload, "auth": auth, "callback_url": callback_url}


@app.task(bind=True)
def send_attendance_to_websocket(self, attendance_id: int, tenant_entity_id: int, attendance_category: str):
    try:
        connection = get_rabbitmq_sync_connection()

        message_body = {
            "attendance_id": attendance_id,
            "tenant_entity_id": tenant_entity_id,
            "attendance_category": attendance_category,
        }

        message_body = json.dumps(message_body)

        channel = connection.channel()

        channel.confirm_delivery()
        channel.basic_publish(exchange="amq.fanout", routing_key="*", body=message_body)
    finally:
        connection.close()


@app.task(bind=True, base=DatabaseTask, max_retries=10)
def add_identity_to_camera(
        self,
        identity_id: int,
        identity_first_name: str,
        identity_photo: str,
        identity_version: int,
        identity_group: int,
        camera_id: int,
        camera_device_id: str,
        camera_password: str,
        tenant_id: int,
        tenant_entity_id: int,
):
    db = self.get_db()
    integration = db.query(Integrations).filter_by(tenant_id=tenant_id, module_id=1).first()
    if integration:
        callback_url = integration.identity_callback_url
        if integration.auth_type.lower() in ["basic", "jwt"] and integration.username and integration.password:
            auth = {"auth": integration.auth_type, "username": integration.username, "password": integration.password}
        elif integration.token:
            auth = {"auth": integration.auth_type, "token": integration.token, "token_type": integration.token_type}
        else:
            auth = None
    else:
        new_error = ErrorSmartCamera(
            identity_id=identity_id,
            smart_camera_id=camera_id,
            error_type="smart_camera",
            error_message="Integration not found",
            error_code=404,
            version=identity_version,
        )
        db.add(new_error)
        db.commit()
        db.refresh(new_error)
        auth, callback_url = None, None
    try:
        url = f"http://{CAMERA_MANAGER_URL}/device/{camera_device_id}/user_management/addUser"
        payload_dict = {
            "password": camera_password,
            "user_id": identity_id,
            "user_list": 2,
            "image_type": "image",
            "image_content": image_url_to_base64(str(identity_photo)),
            "user_info": {"name": identity_first_name},
            "group": identity_group,
        }
        payload = json.dumps(payload_dict)
        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
        )
    except Exception as e:
        data = {
            "message_id": self.request.id,
            "payload": {
                "is_success": False,
                "message": str(e),
                "code": 400,
                "type": "create",
                "version": identity_version,
                "identity_group": identity_group,
                "id": identity_id,
                "identity_first_name": identity_first_name,
                "tenant_entity_id": tenant_entity_id,
            },
            "auth": auth,
            "callback_url": callback_url,
        }
        return on_event(data)
    if response.status_code != 200:  # noqa
        if "already exists" not in response.text:  # noqa
            new_error = ErrorSmartCamera(
                identity_id=identity_id,
                smart_camera_id=camera_id,
                error_type="smart_camera",
                error_message=get_main_error_text(response),
                error_code=response.status_code,
                version=identity_version,
            )
            db.add(new_error)
            db.commit()
            db.refresh(new_error)
            if is_retry(response):
                self.retry(
                    exc=TaskError(f"Failed to add identity to smart camera: {get_main_error_text(response)}"),
                    countdown=3600,
                    max_retries=10,
                )
            data = {
                "message_id": self.request.id,
                "payload": {
                    "is_success": False,
                    "message": get_main_error_text(response),
                    "code": response.status_code,
                    "type": "create",
                    "id": identity_id,
                    "identity_first_name": identity_first_name,
                    "version": identity_version,
                    "identity_group": identity_group,
                    "tenant_entity_id": tenant_entity_id,
                },
                "auth": auth,
                "callback_url": callback_url,
            }
            return on_event(data)
    i_scamera = db.query(IdentitySmartCamera).filter_by(identity_id=identity_id, smart_camera_id=camera_id).first()
    if i_scamera:
        data = {
            "message_id": self.request.id,
            "payload": {
                "is_success": False,
                "message": "User id already exists in smart_camera",
                "code": 400,
                "type": "create",
                "id": identity_id,
                "identity_first_name": identity_first_name,
                "version": identity_version,
                "identity_group": identity_group,
                "tenant_entity_id": tenant_entity_id,
            },
            "auth": auth,
            "callback_url": callback_url,
        }
        return on_event(data)
    new_identity_scamera = IdentitySmartCamera(
        identity_id=identity_id, smart_camera_id=camera_id, version=identity_version
    )
    db.add(new_identity_scamera)
    db.commit()
    db.refresh(new_identity_scamera)
    data = {
        "message_id": self.request.id,
        "payload": {
            "is_success": True,
            "message": "Identity added to camera successfully",
            "code": 200,
            "type": "create",
            "id": identity_id,
            "identity_first_name": identity_first_name,
            "version": identity_version,
            "identity_group": identity_group,
            "tenant_entity_id": tenant_entity_id,
        },
        "auth": auth,
        "callback_url": callback_url,
    }
    return on_event(data)


@app.task(bind=True, base=DatabaseTask, max_retries=10)
def delete_identity_from_smart_camera(
        self,
        identity_id: int,
        identity_first_name: str,
        identity_version: int,
        identity_group: int,
        camera_id: int,
        camera_device_id: str,
        camera_password: str,
        tenant_id: int,
        tenant_entity_id: int,
):
    db = self.get_db()
    integration = db.query(Integrations).filter_by(tenant_id=tenant_id, module_id=1).first()
    if integration:
        callback_url = integration.identity_callback_url
        if integration.auth_type.lower() in ["basic", "jwt"] and integration.username and integration.password:
            auth = {"auth": integration.auth_type, "username": integration.username, "password": integration.password}
        elif integration.token:
            auth = {"auth": integration.auth_type, "token": integration.token, "token_type": integration.token_type}
        else:
            auth = None
    else:
        auth, callback_url = None, None
    try:
        url = f"http://{CAMERA_MANAGER_URL}/device/{camera_device_id}/user_management/deleteUser"
        password = camera_password
        payload = json.dumps({"password": password, "user_id": identity_id, "user_list": 2, "group": identity_group})
        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
        )
    except Exception as e:
        data = {
            "message_id": self.request.id,
            "payload": {
                "is_success": False,
                "message": str(e),
                "code": 400,
                "type": "delete",
                "id": identity_id,
                "identity_first_name": identity_first_name,
                "version": identity_version,
                "identity_group": identity_group,
                "tenant_entity_id": tenant_entity_id,
            },
            "auth": auth,
            "callback_url": callback_url,
        }
        return on_event(data)
    if response.status_code != 200:
        if is_retry(response):
            self.retry(
                exc=TaskError(f"Failed to delete identity from smart camera: {get_main_error_text(response)}"),
                countdown=3600,
                max_retries=10,
            )
        data = {
            "message_id": self.request.id,
            "payload": {
                "is_success": False,
                "message": get_main_error_text(response),
                "code": response.status_code,
                "type": "delete",
                "id": identity_id,
                "identity_first_name": identity_first_name,
                "version": identity_version,
                "identity_group": identity_group,
                "tenant_entity_id": tenant_entity_id,
            },
            "auth": auth,
            "callback_url": callback_url,
        }
        return on_event(data)
    identity_scamera = (
        db.query(IdentitySmartCamera)
        .filter_by(identity_id=identity_id, smart_camera_id=camera_id, is_active=True)
        .first()
    )
    if identity_scamera:
        identity_scamera.is_active = False
        db.commit()
        db.refresh(identity_scamera)
    data = {
        "message_id": self.request.id,
        "payload": {
            "is_success": True,
            "message": "Identity deleted from smart camera successfully",
            "code": 200,
            "type": "delete",
            "id": identity_id,
            "identity_first_name": identity_first_name,
            "version": identity_version,
            "identity_group": identity_group,
            "tenant_entity_id": tenant_entity_id,
        },
        "auth": auth,
        "callback_url": callback_url,
    }
    return on_event(data)


@app.task(bind=True, base=DatabaseTask, max_retries=10)
def add_wanted_to_smart_camera(
        self,
        wanted_id: int,
        wanted_first_name: str,
        wanted_photo: str,
        concern_level: int,
        accusation: str,
        camera_id: int,
        camera_device_id: str,
        camera_password: str,
        tenant_entity_id: int,
):
    db = self.get_db()
    try:
        url = f"http://{CAMERA_MANAGER_URL}/device/{camera_device_id}/user_management/addUser"
        payload_dict = {
            "password": camera_password,
            "user_id": f"w{wanted_id}",
            "user_list": 1,
            "image_type": "image",
            "image_content": image_url_to_base64(str(wanted_photo)),
            "user_info": {"name": wanted_first_name},
            "group": concern_level,
        }
        payload = json.dumps(payload_dict)
        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
        )
    except Exception as e:
        return {"success": False, "error": str(e), "code": 400, "message_id": self.request.id, "type": "add"}
    if response.status_code != 200:  # noqa
        if "already exists" not in response.text:  # noqa
            new_error = ErrorSmartCamera(
                user_id=wanted_id,
                smart_camera_id=camera_id,
                error_type="smart_camera",
                error_message=get_main_error_text(response),
                error_code=response.status_code,
            )
            db.add(new_error)
            db.commit()
            db.refresh(new_error)
            if is_retry(response):
                self.retry(
                    exc=TaskError(f"Failed to add wanted to smart camera: {get_main_error_text(response)}"),
                    countdown=600,
                    max_retries=10,
                )
            return {
                "success": False,
                "error": get_main_error_text(response),
                "code": response.status_code,
                "message_id": self.request.id,
                "type": "add",
            }
    w_scamera = (
        db.query(WantedSmartCamera).filter_by(wanted_id=wanted_id, smart_camera_id=camera_id, is_active=True).first()
    )
    if w_scamera:
        return {
            "success": False,
            "error": "User id already exists in smart camera",
            "code": 400,
            "message_id": self.request.id,
            "type": "add",
        }
    new_wanted_scamera = WantedSmartCamera(wanted_id=wanted_id, smart_camera_id=camera_id)
    db.add(new_wanted_scamera)
    db.commit()
    db.refresh(new_wanted_scamera)
    return {"success": True, "error": None, "code": 200, "message_id": self.request.id, "type": "add"}


@app.task(bind=True, base=DatabaseTask, max_retries=10)
def create_relative_identity_list_task(self, tenant_id: int, data: list):
    db = self.get_db()
    for item in data:
        new_item = RelativeBase(
            first_name=item["first_name"],
            last_name=item["last_name"],
            photo=item["photo"],
            email=item["email"],
            phone=item["phone"],
            pinfl=item["pinfl"],
        )
        relative = create_relative(db, new_item)
        if item["kid_ids"]:
            for kid_id in item["kid_ids"]:
                identity = (
                    db.query(Identity)
                    .filter_by(external_id=str(kid_id), tenant_id=tenant_id, identity_group=0, is_active=True)
                    .first()
                )
                if identity:
                    new_relative_identity = IdentityRelative(identity_id=identity.id, relative_id=relative.id)
                    db.add(new_relative_identity)
                    db.commit()
                    db.refresh(new_relative_identity)


@app.task(bind=True, base=DatabaseTask)
def update_relative_photo_with_pinfl_task(self, relative_id: int, tenant_id: int):
    db = self.get_db()
    relative = get_relative(db, relative_id)
    result = get_user_photo_by_pinfl(pinfl=relative.pinfl)
    if result["success"]:
        try:
            main_image = get_image_from_query(result["photo"])
            main_photo_url = make_minio_url_from_image(
                minio_client, main_image, RELATIVE_IDENTITY_BUCKET, relative.pinfl, is_check_hd=False
            )
            relative.photo = main_photo_url
            db.commit()
            db.refresh(relative)
        except Exception as e:
            logger.info(f"update_relative_photo_with_pinfl_task, error: {e}")


@app.task(bind=True, base=DatabaseTask)
def upload_relative_with_task(self, relative_id: int, tenant_id: int, tenant_entity_id: int):
    db = self.get_db()
    relative = get_relative(db, relative_id)
    smart_cameras = db.query(SmartCamera.id).filter_by(tenant_entity_id=tenant_entity_id, is_active=True).all()
    for smart_camera in smart_cameras:
        relative_smart_camera = (
            db.query(RelativeSmartCamera)
            .filter_by(relative_id=relative.id, smart_camera_id=smart_camera.id, is_active=True)
            .first()
        )
        if not relative_smart_camera:
            create_task_to_scamera(db, "add_relative", smart_camera.id, relative_id, "relative")


@app.task(bind=True, base=DatabaseTask)
def child_implementation_task(self, relative_id: int, data: list):
    db: Session = self.get_db()
    for child in data:
        identity = (
            db.query(Identity)
            .filter_by(pinfl=child["kid_pinfl"], external_id=str(child["kid_id"]), identity_group=0, is_active=True)
            .first()
        )
        if identity:
            identity.pinfl = child["kid_pinfl"]
            identity.metrics = child["kid_metrics"]
            db.commit()
            identity_relative = (
                db.query(IdentityRelative)
                .filter_by(identity_id=identity.id, relative_id=relative_id, is_active=True)
                .first()
            )
            if not identity_relative:
                new_identity_relative = IdentityRelative(identity_id=identity.id, relative_id=relative_id)
                db.add(new_identity_relative)
                db.commit()
            tenant_entity = db.query(TenantEntity).filter_by(id=identity.tenant_entity_id, is_active=True).first()
            if tenant_entity:
                tenant_entity.kassa_id = child["kassa_id"]
                db.commit()


@app.task(bind=True, base=DatabaseTask, max_retries=3)
def send_attendance_to_platon_task(
        self, tenant_id: int, mtt_id: int, tenant_entity_id: int, identity_group: int, date: str
):
    db = self.get_db()
    _date = datetime.strptime(date, "%Y-%m-%d")
    start_date, end_date = _date, _date + timedelta(days=1)
    attendances = (
        db.query(Attendance)
        .join(Identity, Identity.id == Attendance.identity_id)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .filter(
            and_(
                Attendance.tenant_entity_id == tenant_entity_id,
                Attendance.attendance_datetime >= start_date,
                Attendance.attendance_datetime < end_date,
                Identity.identity_group == identity_group,
            )
        )
        .all()
    )
    data = []
    for attendance in attendances:
        if attendance.snapshot_url:
            item = {
                "identity_id": int(attendance.identity.external_id),
                "identity_group": attendance.identity.identity_group,
                "mtt_id": mtt_id,
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
                "tenant_id": tenant_id,
                "image_url": attendance.snapshot_url,
                "package_uuid": attendance.package_uuid,
                "version": attendance.version,
                "username": attendance.username,
            }
            data.append(item)
    for i in range(0, len(data), 15):
        print(i, 15)
        chunk = data[i: i + 15]
        start_time = datetime.now()
        r = requests.post(
            url="https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits_batch",
            headers=batch_attendance_basic_auth,
            json={"identity_group": identity_group, "tenant_id": tenant_id, "results": chunk},
        )
        end_time = datetime.now()
        print(f"spent_time(send_attendance_to_platon_task): {(end_time - start_time).total_seconds():.2f} s")
        if r.status_code == 200:
            print(f"mtt_id: {mtt_id}, identity_group: {identity_group}, count: {len(chunk)}, SUCCESS POST")
        else:
            print(f"mtt_id: {mtt_id}, identity_group: {identity_group}, count: {len(chunk)}, FAILED POST")


@app.task(
    bind=True, base=Batches, max_batch_size=40, flush_every=30, flush_interval=10, queue="send_express_attendance_queue"
)
def send_express_attendance_batch(self, _tasks: list):
    # send_express_attendance_batch.delay(data={"some": "data"}) example of calling the task
    nmmt_batch_kids = {"identity_group": 0, "tenant_id": 18, "results": []}
    dmmt_batch_kids = {"identity_group": 0, "tenant_id": 1, "results": []}
    nmtt_batch_emps = {"identity_group": 1, "tenant_id": 18, "results": []}
    dmtt_batch_emps = {"identity_group": 1, "tenant_id": 1, "results": []}
    for _task in _tasks:
        item = _task.kwargs["data"]
        if item["identity_group"] == 1:
            if item["tenant_id"] == 18:
                nmtt_batch_emps["results"].append(item)
            else:
                dmtt_batch_emps["results"].append(item)
        else:
            if item["tenant_id"] == 18:
                nmmt_batch_kids["results"].append(item)
            else:
                dmmt_batch_kids["results"].append(item)
    for batch_data in [nmmt_batch_kids, dmmt_batch_kids, nmtt_batch_emps, dmtt_batch_emps]:
        if not batch_data["results"]:
            continue
        start_time = datetime.now()
        r = requests.post(
            url="https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits_batch",
            headers=batch_attendance_basic_auth,
            json=batch_data,
        )
        end_time = datetime.now()
        print(f"spent_time(send_attendance_to_platon_task): {(end_time - start_time).total_seconds():.2f} s")
        try:
            r.raise_for_status()
            print(f"identity_group: {batch_data['identity_group']}, count: {len(batch_data['results'])}, SUCCESS POST")
        except RequestException as e:
            sentry_sdk.capture_exception(e)


@app.task(bind=True, queue="send_updated_identity_photo_queue")
def send_updated_identity_photo_task(self, data: dict):
    identity_group = data["identity_group"]
    photo_url = data["photo_url"]
    upload_path = "files/upload/category/educators" if identity_group == 1 else "files/upload/category/kids"
    try:
        image_bytes = get_image_from_url(photo_url)
        with tempfile.NamedTemporaryFile(suffix=".jpeg") as temp_file:
            temp_file.write(image_bytes)
            temp_file.flush()  # Ensure all data is written to disk
            temp_file.seek(0)
            files = {"file": (temp_file.name, temp_file, "image/jpeg")}
            r = requests.post(
                url=NODAVLAT_BASE_URL + upload_path,
                headers=BASIC_AUTH,
                files=files,
                timeout=30,
            )
            if r.status_code != 200:
                return {"success": False, "error": r.text}
            photo_id = r.json()["id"]
    except Exception as e:
        print(f"upload_identity_photo_to_platon error: {e}")
        return {"success": False, "error": str(e)}
    try:
        mtt_id = data.get("mtt_id")
        _id = data.get("_id")
        tenant_id = data.get("tenant_id")
        photo_pk = data.get("photo_pk")
        json_data = {
            "mtt_id": mtt_id,
            "photo": photo_id,
            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "photo_pk": photo_pk,
            "username": data.get("username"),
        }
        update_item = {"kid_id": int(_id)} if identity_group == 0 else {"educator_id": int(_id)}
        json_data.update(update_item)
        path = "api/v1/realsoftai/mtt/kid/photo"
        if identity_group == 1:
            path = "api/v1/realsoftai/dmtt/edu/photo" if tenant_id == 1 else "api/v1/realsoftai/nmtt/edu/photo"
        r = requests.post(url=NODAVLAT_BASE_URL + path, headers=BASIC_AUTH, json=json_data, timeout=30)
        if r.status_code != 200:
            return {"success": False, "error": r.text}
    except Exception as e:
        print(f"send_photo_to_platon error: {e}")
        return {"success": False, "error": str(e)}
    return {"success": True, "error": None}


@app.task(bind=True, base=DatabaseTask)
def send_identity_photo_history(self, data: dict):
    if data["is_main"]:
        try:
            image_hdd = minio_client.get_object(data["bucket"], data["object_name"])  # noqa
        except S3Error as err1:
            if err1.code == "NoSuchKey":
                try:
                    image_ssd = minio_ssd_client.get_object(data["bucket"], data["object_name"])  # noqa
                except S3Error as err2:
                    if err2.code == "NoSuchKey":
                        db = self.get_db()
                        stmt = (
                            update(Identity)
                            .where(Identity.id == data["identity_id"])
                            .values(photo=None, embedding512=None, cropped_image512=None, version=Identity.version + 1)
                        )
                        db.execute(stmt)
                        db.commit()
                        print("handled no_such_key")

    del data["identity_id"]
    del data["bucket"]
    del data["object_name"]

    if not data["photo_id"]:
        identity_group = data["identity_group"]
        photo_url = data["photo_url"]
        upload_path = "files/upload/category/educators" if identity_group == 1 else "files/upload/category/kids"
        try:
            image_bytes = get_image_from_url(photo_url)
            with tempfile.NamedTemporaryFile(suffix=".jpeg") as temp_file:
                temp_file.write(image_bytes)
                temp_file.flush()  # Ensure all data is written to disk
                temp_file.seek(0)
                files = {"file": (temp_file.name, temp_file, "image/jpeg")}
                r = requests.post(
                    url=NODAVLAT_BASE_URL + upload_path,
                    headers=BASIC_AUTH,
                    files=files,
                    timeout=10,
                )
                if r.status_code != 200:
                    return {"success": False, "error": r.text}
                photo_id = r.json()["id"]
                data["photo_id"] = photo_id
        except Exception as e:
            print(f"send_identity_photo_history: upload_identity_photo_to_platon error: {e}")
            return {"success": False, "error": str(e)}
    try:
        url = "https://api.nodavlat-bogcha.uz/api/v1/realsoftai/kid/edu/photo"
        r = requests.post(url=url, headers=BASIC_AUTH, json=data, timeout=10)
        if r.status_code != 200:
            return {"success": False, "error": r.text}
    except Exception as e:
        print(f"send_identity_photo_history error: {e}")
        return {"success": False, "error": str(e)}
    return {"success": True, "error": None}


@app.task(bind=True, base=DatabaseTask)
def send_attendance_by_identity_task(
        self, mtt_id: int, identity_id: int, external_id: str, start_str: str, end_str: str
):
    start_time = datetime.strptime(start_str, "%Y-%m-%dT%H:%M:%S")
    end_time = datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S")
    db = self.get_db()
    attendances = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .filter(
            and_(
                Attendance.identity_id == identity_id,
                Attendance.attendance_datetime >= start_time,
                Attendance.attendance_datetime < end_time,
                Attendance.mismatch_entity.is_not(True),
                Attendance.snapshot_url.is_not(None),
                Attendance.is_active,
            )
        )
        .all()
    )
    for attendance in attendances:
        package_verified = False
        if attendance.package_id:
            package = db.query(Package).filter_by(id=attendance.package_id, is_active=True).first()
            if package:  # noqa
                if package.appLicensingVerdict == "LICENSED" and package.appRecognitionVerdict == "PLAY_RECOGNIZED":  # noqa
                    package_verified = True
        result = {
            "identity_id": int(external_id),
            "identity_group": attendance.identity.identity_group,
            "mtt_id": mtt_id,
            "group_id": attendance.identity.group_id,
            "created_at": attendance.attendance_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
            "attendance_id": attendance.id,
            "position_id": attendance.position_id,
            "lat": attendance.lat,
            "lon": attendance.lon,
            "app_version": attendance.app_version_name,
            "device_model": attendance.device_model,
            "device_ip": attendance.device_ip,
            "is_spoofed": attendance.spoofing.is_spoofed,
            "spoofing_score": attendance.spoofing.score,
            "spoofing_bucket": attendance.bucket_name,
            "spoofing_object_name": attendance.object_name,
            "tenant_id": attendance.tenant_id,
            "image_url": attendance.snapshot_url,
            "package_uuid": attendance.package_uuid,
            "version": attendance.version,
            "package_verified": package_verified,
            "username": attendance.username,
        }
        try:
            start_time = datetime.now()
            r = requests.post(
                url="https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits",
                json={"status": "SUCCESS", "result": result},
                timeout=10,
            )
            end_time = datetime.now()
            print(f"spent_time(send_attendance_by_identity_task): {(end_time - start_time).total_seconds():.2f} s")
            if r.status_code != 200:
                print(f"Failed to send_attendance_by_identity_task({r.status_code}): " + r.text)
        except Exception as e:
            print(f"Failed to send_attendance_by_identity_task: {e}")


class PredictTask(Task):
    abstract = True
    _db_session: Session = None

    def after_return(self, *args, **kwargs):
        if self._db_session:
            self._db_session.close()
            self._db_session = None

    def get_db(self) -> Session:
        if not self._db_session:
            self._db_session = SessionLocal()
        return self._db_session

    def on_success(self, retval, task_id, args, kwargs):
        print("Task succeeded")
        # if self.__qualname__ == "spoofing_check_task" or self.__qualname__ == "check_for_similar_faces":
        # callback_url = kwargs.get("callback_endpoint")
        callback_url = "https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits"

        if callback_url:
            self.send_success_callback(callback_url, retval)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print("Task failed")
        if self.__qualname__ == "spoofing_check_task":
            callback_url = kwargs.get("on_failure_callback_endpoint")
            kid_id = kwargs.get("kid_id")
            mtt_id = kwargs.get("mtt_id")
            bucket = kwargs.get("bucket")
            object_name = kwargs.get("object_name")
            created_at = kwargs.get("created_at")

            _error = {
                "error": str(exc),
                "kid_id": kid_id,
                "mtt_id": mtt_id,
                "bucket": bucket,
                "object_name": object_name,
                "created_at": created_at,
            }

            if callback_url:
                self.send_failure_callback(callback_url, _error)

        elif self.__qualname__ == "check_for_similar_faces":
            callback_url = kwargs.get("on_failure_callback_endpoint")

            _error = {
                "message": str(exc),
                "kid_id": kwargs.get("kid_id"),
                "mtt_id": kwargs.get("mtt_id"),
            }

            if callback_url:
                self.send_failure_callback(callback_url, _error)

    @staticmethod
    def send_success_callback(callback_url, result):
        print("Sending success callback")
        print("callback_url", callback_url)
        try:
            result = jsonable_encoder(result)

            start_time = time.time()
            print(f"start_time(send_spoofing_result): {datetime.now()}")
            res = requests.post(callback_url, json={"status": "SUCCESS", "result": result})
            print(f"end_time(send_spoofing_result): {datetime.now()}")
            end_time = time.time()
            print(f"Time taken to send callback: {(end_time - start_time) * 1000}" + "ms")
            print("################################# SEND CALLBACK #################################")
            print(f"########### DATA: {result}")
            print(f"########## RESPONSE STATUS CODE {res.status_code}")
            # print(f"########## RESPONSE FROM THE SERVER {res.json()}")
            # if res.status_code != 200:
            #     data = {
            #         "success": True,
            #         "status_code": res.status_code,
            #         "response": res.json(),
            #         "result": result,
            #     }
            #     mongo_client["mobile-attendance"]["callback_logs"].insert_one(data)
            #     print("Failed to send callback: " + str(res.status_code))
        except Exception as e:
            # data = {"success": True, "status_code": 500, "response": str(e), "result": result}
            # mongo_client["mobile-attendance"]["callback_logs"].insert_one(data)
            print("Failed to send callback: " + str(e))

    @staticmethod
    def send_failure_callback(callback_url, error):
        print("Sending failure callback")
        try:
            start_time = time.time()
            res = requests.post(callback_url, json={"status": "FAILED", "error": error})
            end_time = time.time()
            print(f"Time taken to send callback: {(end_time - start_time) * 1000}" + "ms")
            if res.status_code != 200:
                data = {"success": False, "status_code": res.status_code, "response": res.json(), "error": error}
                mongo_client["mobile-attendance"]["callback_logs"].insert_one(data)
                print("Failed to send callback: " + str(res.status_code))
        except Exception as e:
            data = {"success": False, "status_code": 500, "response": str(e), "error": error}
            mongo_client["mobile-attendance"]["callback_logs"].insert_one(data)
            print("Failed to send callback: " + str(e))


@app.task(bind=True, base=DatabaseTask)
def send_attendance_leftovers_to_platon_beat_task(self):
    db = self.get_db()
    today = datetime.now().date().strftime("%Y-%m-%d")
    for tenant_id in [1, 18]:  # 1 - DMTT, 18 - NMTT
        for district_id in range(1, 210):  # 1 - 209 district ids in Uzbekistan
            tenant_entities = (
                db.query(TenantEntity.id, TenantEntity.external_id)
                .filter(
                    TenantEntity.tenant_id == tenant_id,
                    TenantEntity.district_id == district_id,
                    TenantEntity.hierarchy_level == 3,
                    TenantEntity.is_active,
                )
                .all()
            )
            job = group(
                [
                    send_attendance_leftovers_to_platon_task.s(tenant_id, tenant_entity.external_id, today)
                    for tenant_entity in tenant_entities
                ]
            )
            job.apply_async()


def send_attendance_leftovers_to_platon_service(db: Session, tenant_id: int, mtt_id: int, attendance_date: datetime):
    start_date = attendance_date.replace(hour=0, minute=0, second=0)
    end_date = attendance_date.replace(hour=23, minute=59, second=59)
    tenant_entity = db.query(TenantEntity.id).filter_by(external_id=mtt_id, tenant_id=tenant_id, is_active=True).first()
    path = f"api/v1/realsoftai/mtt/visits_sync?mtt_id={mtt_id}&visit_date={attendance_date.strftime('%Y-%m-%d')}"
    r = requests.get(url=NODAVLAT_BASE_URL + path, headers=BASIC_AUTH)
    if r.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=r.text)
    external_ids = r.json()["data"]["edus"] + r.json()["data"]["kids"]
    identity_data = (
        db.query(Attendance.identity_id, func.max(Identity.external_id).label("max_external_id"))
        .join(Identity, Identity.id == Attendance.identity_id)
        .filter(
            and_(
                Attendance.tenant_entity_id == tenant_entity.id,
                Attendance.attendance_datetime >= start_date,
                Attendance.attendance_datetime < end_date,
                Attendance.snapshot_url.is_not(None),
                Attendance.mismatch_entity.is_not(True),
                Attendance.is_active,
                Identity.is_active,
            )
        )
        .group_by(Attendance.identity_id)
        .all()
    )
    unsent_count = 0
    for item in identity_data:
        if item[1] not in external_ids:
            send_attendance_by_identity_task.delay(
                mtt_id,
                item[0],
                item[1],
                start_date.strftime("%Y-%m-%dT%H:%M:%S"),
                end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            )
            unsent_count += 1
    return unsent_count


@app.task(bind=True, base=DatabaseTask, max_retries=3)
def send_attendance_leftovers_to_platon_task(self, tenant_id: int, mtt_id: int, attendance_date: str):
    db = self.get_db()
    attendance_date = datetime.strptime(attendance_date, "%Y-%m-%d")
    try:
        send_attendance_leftovers_to_platon_service(
            db=db, tenant_id=tenant_id, mtt_id=mtt_id, attendance_date=attendance_date
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise self.retry(exc=e, countdown=600) from e


class DatabaseBatchTask(DatabaseTask, Batches):
    """
    A custom base class that merges:
      - PredictTask (your DB logic)
      - Batches (Celery's batch processing logic)
    """

    abstract = True

    # Optionally, you can override methods here if you need to
    # but usually the above "PredictTask" logic + "Batches" is enough.
    # Just remember to call super() if you override `after_return`
    # or other methods so both parents can run their code.
    def after_return(self, *args, **kwargs):
        # Your custom code if needed
        super().after_return(*args, **kwargs)  # ensures DB gets closed, etc.


@app.task(
    bind=True,
    base=DatabaseBatchTask,
    max_retries=3,
    max_batch_size=40,
    flush_every=30,
    flush_interval=10,
    ignore_result=False,
    default_retry_delay=100,
    queue="spoofing_check_task",
)
def spoofing_check_task(self, _tasks: list):
    nmmt_batch_kids = {"identity_group": 0, "tenant_id": 18, "results": []}
    dmmt_batch_kids = {"identity_group": 0, "tenant_id": 1, "results": []}
    nmtt_batch_emps = {"identity_group": 1, "tenant_id": 18, "results": []}
    dmtt_batch_emps = {"identity_group": 1, "tenant_id": 1, "results": []}
    db = self.get_db()
    try:
        for _task in _tasks:
            item = _task.kwargs["data"]
            image_list = []
            result = minio_ssd_client.get_object(item["bucket"], item["object_name"])
            image_array, image_array_raw = pre_process_image(result, image_list=image_list)
            inputs = [grpcclient.InferInput("inception_v3_input", image_array.shape, "FP32")]
            inputs[0].set_data_from_numpy(image_array)
            outputs = [grpcclient.InferRequestedOutput("dense_2")]
            results = triton_client.infer(model_name="anti_spoofing_trition_model", inputs=inputs, outputs=outputs)
            results = results.as_numpy("dense_2")
            fake_score = round(results[0][0], 3)
            real_score = round(results[0][1], 3)
            spoofing_threshold = item["spoofing_threshold"] or 0.98
            is_spoofed = bool(fake_score > spoofing_threshold)
            score = fake_score if is_spoofed else real_score

            att_spoofing = (
                db.query(AttendanceAntiSpoofing).filter_by(id=item["attendance_spoofing_id"], is_active=True).first()
            )
            att_spoofing.is_spoofed = is_spoofed
            att_spoofing.score = float(score)
            att_spoofing.real_score = float(real_score)
            att_spoofing.fake_score = float(fake_score)
            db.commit()
            db.refresh(att_spoofing)
            attendance = db.query(Attendance).filter_by(id=att_spoofing.attendance_id, is_active=True).first()
            attendance.version += 1
            attendance.has_warning = is_spoofed
            db.commit()
            db.refresh(attendance)

            old_image = minio_ssd_client.get_object(item["bucket"], item["object_name"])
            pil_image = PIL.Image.open(old_image)
            buffer = io.BytesIO()
            if pil_image.mode != "RGB":
                pil_image = pil_image.convert("RGB")
            pil_image.save(buffer, format="JPEG", quality=50, optimize=True)
            buffer.seek(0)
            if is_spoofed:
                minio_client.put_object(
                    bucket_name=MINIO_COMPROMISED_SPOOF,
                    object_name=item["object_name"],
                    data=buffer,
                    length=buffer.getbuffer().nbytes,
                    content_type="image/jpeg",
                )
                image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{MINIO_COMPROMISED_SPOOF}/{item['object_name']}"
            else:
                minio_client.put_object(
                    bucket_name=MINIO_CLEAR_SPOOF,
                    object_name=item["object_name"],
                    data=buffer,
                    length=buffer.getbuffer().nbytes,
                    content_type="image/jpeg",
                )
                image_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{MINIO_CLEAR_SPOOF}/{item['object_name']}"
            attendance.snapshot_url = image_url
            attendance.bucket_name = MINIO_COMPROMISED_SPOOF if is_spoofed else MINIO_CLEAR_SPOOF
            db.commit()
            db.refresh(attendance)
            minio_ssd_client.remove_object(item["bucket"], item["object_name"])
            identity = (
                db.query(Identity)
                .filter_by(id=item["identity_id"], tenant_entity_id=attendance.tenant_entity_id)
                .first()
            )
            response = {
                "identity_id": int(item["kid_id"]),
                "identity_group": identity.identity_group,
                "mtt_id": item["mtt_id"],
                "group_id": identity.group_id,
                "created_at": item["created_at"],
                "attendance_id": attendance.id if attendance else None,
                "position_id": attendance.position_id if attendance else None,
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "app_version": item["app_version_name"],
                "device_model": item["device_model"],
                "device_ip": item["device_ip"],
                "is_spoofed": is_spoofed,
                "spoofing_score": float(score),
                "spoofing_bucket": MINIO_COMPROMISED_SPOOF if is_spoofed else MINIO_CLEAR_SPOOF,
                "spoofing_object_name": item["object_name"],
                "tenant_id": identity.tenant_id,
                "image_url": image_url,
                "package_uuid": attendance.package_uuid,
                "version": attendance.version,
                "package_verified": item["package_verified"],
                "username": attendance.username,
            }

            try:
                task_id = self.request.id

                response.update({"task_id": task_id})
                response.update({"date": datetime.now().isoformat()})

                mongo_client["face_analytics"]["spoofing_check_responses_individual"].insert_one(response)

                response.pop("_id")
                response.pop("date")
            except Exception as e:
                print(f"Error in saving response: {e}")

            if response["identity_group"] == 1:
                if response["tenant_id"] == 18:
                    nmtt_batch_emps["results"].append(response)
                else:
                    dmtt_batch_emps["results"].append(response)
            else:
                if response["tenant_id"] == 18:
                    nmmt_batch_kids["results"].append(response)
                else:
                    dmmt_batch_kids["results"].append(response)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        gc.collect()
        raise self.retry(exc=e, countdown=1800) from e
    for batch_data in [nmmt_batch_kids, dmmt_batch_kids, nmtt_batch_emps, dmtt_batch_emps]:
        if not batch_data["results"]:
            continue
        start_time = datetime.now()
        r = requests.post(
            url="https://mq.nodavlat-bogcha.uz/api/call/v4/kindergartens/kids_visits_batch",
            headers=batch_attendance_basic_auth,
            json=batch_data,
        )
        end_time = datetime.now()
        print(f"spent_time(kids_visits_batch(spoofing)): {(end_time - start_time).total_seconds():.2f} s")
        try:
            r.raise_for_status()
            print(f"identity_group: {batch_data['identity_group']}, scount: {len(batch_data['results'])}, SUCCESS POST")
        except RequestException as e:
            sentry_sdk.capture_exception(e)


@worker_process_init.connect
def init_worker(**kwargs):
    MONGO_DB_URL = os.environ.get("MONGODB_URL")
    TRITON_URL = os.environ.get("TRITON_URL")

    global triton_client
    triton_client = grpcclient.InferenceServerClient(url=TRITON_URL, verbose=False)
    print("Connected to triton")
    global mongo_client

    print("Initializing database connection for worker.")

    mongo_client = MongoClient(MONGO_DB_URL)


@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    global mongo_client
    print("Closing database connection for worker.")
    mongo_client.close()
