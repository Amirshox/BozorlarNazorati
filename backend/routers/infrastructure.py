import base64
import io
import json
import os
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from math import ceil
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, File, HTTPException, Query, Security, UploadFile, status
from fastapi.responses import FileResponse
from fastapi_pagination.ext.sqlalchemy import paginate
from jinja2 import Environment, FileSystemLoader
from pymongo import ASCENDING
from requests import Response
from sqlalchemy import and_, distinct, func
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin, is_authenticated
from database import (
    db_building,
    db_camera,
    db_jetson,
    db_room,
    db_smartcamera,
)
from database.database import get_logs_db, get_mongo_db, get_pg_db
from database.minio_client import get_minio_client
from models import (
    Attendance,
    Building,
    IdentitySmartCamera,
    Room,
    SmartCamera,
    SmartCameraSnapshot,
    SmartCameraTask,
    TenantEntity,
)
from schemas.attendance import AttendanceInDB, WantedAttendanceInDB
from schemas.infrastructure import (
    BuildingBase,
    BuildingInDB,
    CameraBase,
    CameraCreate,
    CameraInDB,
    CameraSnapshotInDB,
    CustomPaginatedResponseForSmartCamera,
    FirmwareBase,
    FirmwareUpdate,
    IdentityAttendanceAnalyticsForSmartCamera,
    JetsonBase,
    JetsonDeviceSetUpConfigs,
    JetsonInDB,
    JetsonProfileCreate,
    JetsonProfileInDB,
    JetsonProfileRegisterDevice,
    JetsonProfileUpdate,
    RoomBase,
    RoomInDB,
    SetFaceConfigData,
    SetPlatformServerScheme,
    SetRebootConfScheme,
    SetVPNConfScheme,
    SetWiredNetworkScheme,
    SmartCameraBase,
    SmartCameraForMap,
    SmartCameraHealthList,
    SmartCameraInDB,
    SmartCameraNotCreated,
    SmartCameraProfileBase,
    SmartCameraSnapshotFullInDB,
    SmartCameraSnapshotInDB,
)
from schemas.tenant import FirmwareInDB, SmartCameraProfileInDB
from schemas.visitor import VisitorAttendanceInDB
from utils.generator import generate_md5, generate_password
from utils.image_processing import get_image_from_url, get_main_error_text
from utils.log import timeit
from utils.pagination import CustomPage
from utils.redis_cache import get_from_redis, get_redis_connection, set_to_redis

router = APIRouter(prefix="/infrastructure", tags=["infrastructure"])

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")

MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")
SNAPSHOT_SCAMERA_BUCKET = os.getenv("SNAPSHOT_SCAMERA_BUCKET", "snapshot-scamera")
IMG_BUCKET = os.getenv("IMG_BUCKET", "img")

HLS_CONVERTOR_PATH = "https://api.realsoft.ai/sysadmin/rtsp_manager/rtsp_to_hls"

global_minio_client = get_minio_client()
if not global_minio_client.bucket_exists(IMG_BUCKET):
    global_minio_client.make_bucket(IMG_BUCKET)
if not global_minio_client.bucket_exists(SNAPSHOT_SCAMERA_BUCKET):
    global_minio_client.make_bucket(SNAPSHOT_SCAMERA_BUCKET)

template_dir = os.path.abspath(os.path.dirname(__file__))
jinja_env = Environment(loader=FileSystemLoader(template_dir))


@router.get("/building/list", response_model=List[BuildingInDB])
def get_buildings_no_pagination(
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_building.get_all_buildings_no_pagination(db, tenant_admin.tenant_id, is_active)


@router.get("/building", response_model=CustomPage[BuildingInDB])
def get_buildings(
    search: Optional[str] = None,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_building.get_all_buildings(db, tenant_admin.tenant_id, search, is_active)
    return paginate(query_set)


@router.get("/building/{pk}", response_model=BuildingInDB)
def get_building(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_building.get_building(db, pk, tenant_admin.tenant_id, is_active)


@router.post("/building", response_model=BuildingInDB)
def create_building(
    building: BuildingBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_building.create_building(db, building, tenant_admin.tenant_id)


@router.put("/building/{pk}", response_model=BuildingInDB)
def update_building(
    pk: int,
    building: BuildingBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_building.update_building(db, pk, building, tenant_admin.tenant_id)


@router.delete("/building/{pk}", response_model=BuildingInDB)
def delete_building(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_building.delete_building(db, pk, tenant_admin.tenant_id)


@router.get("/room/list", response_model=List[RoomInDB])
def get_rooms_no_pagination(
    building_id: Optional[int] = None,
    tenant_entity_id: Optional[int] = None,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_room.get_rooms_by_filter(
        db=db,
        tenant_id=tenant_admin.tenant_id,
        building_id=building_id,
        tenant_entity_id=tenant_entity_id,
        is_active=is_active,
    )


@router.get("/room", response_model=CustomPage[RoomInDB])
def get_rooms(
    building_id: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_room.get_rooms(db, building_id, tenant_admin.tenant_id, is_active)
    return paginate(query_set)


@router.get("/room/{pk}", response_model=RoomInDB)
def get_room(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_room.get_room(db, pk, tenant_admin.tenant_id, is_active)


@router.post("/room", response_model=RoomInDB)
def create_room(
    room: RoomBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_room.create_room(db, room, tenant_admin.tenant_id)


@router.put("/room/{pk}", response_model=RoomInDB)
def update_room(
    pk: int,
    room: RoomBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_room.update_room(db, pk, room, tenant_admin.tenant_id)


@router.delete("/room/{pk}", response_model=RoomInDB)
def delete_room(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_room.delete_room(db, pk)


@router.get("/camera/snapshots", response_model=CustomPage[CameraSnapshotInDB])
def get_camera_snapshots(
    camera_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_camera.get_camera_snapshots(db, camera_id, tenant_admin.tenant_id)
    return paginate(query_set)


# @router.get("/camera", response_model=CustomPage[CameraInDB])
# def get_cameras(
#     room_id: int,
#     is_active: Optional[bool] = Query(default=True, alias="is_active"),
#     db: Session = Depends(get_pg_db),
#     tenant_admin=Security(get_current_tenant_admin),
# ):
#     query_set = db_camera.get_cameras(db, room_id, tenant_admin.tenant_id, is_active)
#     return paginate(query_set)


@router.get("/camera", response_model=CustomPage[CameraInDB])
def get_cameras_by_option(
    building_id: Optional[int] = None,
    room_id: Optional[int] = None,
    is_active: bool = True,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    if building_id:
        query_set = db_camera.get_cameras_by_option(
            db=db, id=building_id, selection_type="building", is_active=is_active
        )
    else:
        query_set = db_camera.get_cameras_by_option(db=db, id=room_id, selection_type="room", is_active=is_active)

    return paginate(query_set)


@router.get("/camera/{pk}", response_model=CameraInDB)
def get_camera(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_camera.get_camera(db, pk, tenant_admin.tenant_id, is_active)


@router.post("/camera", response_model=CameraInDB)
def create_camera(
    camera: CameraCreate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_camera.create_camera(db, camera, tenant_admin.tenant_id)


@router.put("/camera/{pk}", response_model=CameraInDB)
def update_camera(
    pk: int,
    camera: CameraBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_camera.update_camera(db, pk, camera, tenant_admin.tenant_id)


@router.delete("/camera/{pk}", response_model=CameraInDB)
def delete_camera(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_camera.delete_camera(db, pk)


@router.post("/smartcamera/upload_img")
def upload_img(file: UploadFile = File(...), minio_client=Depends(get_minio_client)):
    try:
        file_extension = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_bytes = file.file.read()
        file.file.seek(0)
        minio_client.put_object(IMG_BUCKET, file_name, file.file, len(file_bytes))
        return {"file_name": file_name, "file_url": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{IMG_BUCKET}/{file_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/smartcamera/profile", response_model=SmartCameraProfileInDB)
def create_profile(
    data: SmartCameraProfileBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.create_profile(db, tenant_admin.tenant_id, data)


@router.get("/smartcamera/profile", response_model=List[SmartCameraProfileInDB])
def get_profiles(
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.get_profiles(db, tenant_admin.tenant_id, is_active)


@router.get("/smartcamera/profile/{pk}", response_model=SmartCameraProfileInDB)
def get_profile(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.get_profile(db, pk, tenant_admin.tenant_id, is_active)


@router.put("/smartcamera/profile/{pk}", response_model=SmartCameraProfileInDB)
def update_profile(
    pk: int,
    data: SmartCameraProfileBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.update_profile(db, pk, tenant_admin.tenant_id, data)


@router.delete("/smartcamera/profile/{pk}", response_model=SmartCameraProfileInDB)
def delete_profile(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.delete_profile(db, pk, tenant_admin.tenant_id)


@router.post("/smartcamera/firmware_by_file", response_model=FirmwareInDB)
async def create_firmware_by_file(
    name: str,
    description: Optional[str] = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    uniqi_id = str(uuid.uuid4())
    file_extension = file.filename.split(".")[-1]
    file_name = f"{await generate_md5(uniqi_id)}.{file_extension}"
    image = file.file.read()
    file.file.seek(0)
    minio_client.put_object(IMG_BUCKET, file_name, file.file, len(image))
    file_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{IMG_BUCKET}/{file_name}"
    data = FirmwareBase(name=name, description=description, img=file_url)
    return db_smartcamera.create_firmware(db, tenant_admin.tenant_id, data)


@router.post("/smartcamera/firmware", response_model=FirmwareInDB)
def create_firmware(
    data: FirmwareBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    file_io = io.BytesIO(get_image_from_url(data.img))
    file_name = f"{uuid.uuid4()}.img"
    minio_client.put_object(IMG_BUCKET, str(file_name), file_io, len(file_io.getvalue()))
    file_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{IMG_BUCKET}/{file_name}"
    data.img = file_url
    return db_smartcamera.create_firmware(db, tenant_admin.tenant_id, data)


@router.get("/smartcamera/firmware", response_model=List[FirmwareInDB])
def get_firmwares(
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.get_firmwares(db, tenant_admin.tenant_id, is_active)


@router.get("/smartcamera/firmware/{pk}", response_model=FirmwareInDB)
def get_firmware(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.get_firmware(db, pk, tenant_admin.tenant_id, is_active)


@router.put("/smartcamera/firmware/{pk}", response_model=FirmwareInDB)
def update_firmware(
    pk: int, data: FirmwareUpdate, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_smartcamera.update_firmware(db, pk, tenant_admin.tenant_id, data)


@router.delete("/smartcamera/firmware/{pk}", response_model=FirmwareInDB)
def delete_firmware(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.delete_firmware(db, pk, tenant_admin.tenant_id)


@router.get("/smartcamera/profile_firmware")
def assign_profile_scameras_by_firmware(
    profile_id: int,
    firmware_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    profile = db_smartcamera.get_profile(db, profile_id, tenant_admin.tenant_id)
    # firmware = db_smartcamera.get_firmware(db, firmware_id, tenant_admin.tenant_id)
    scameras = db_smartcamera.get_scameras_by_profile(db, profile.id)
    # for smart_camera in scameras:
    #     new_task = SmartCameraTask(task_type="assign", smart_camera_id=smart_camera.id)
    #     db.add(new_task)
    #     db.commit()
    #     db.refresh(new_task)
    #     new_firmware_scamera = SmartCameraFirmware(firmware_id=firmware.id, smart_camera_id=smart_camera.id)
    #     db.add(new_firmware_scamera)
    #     db.commit()
    #     db.refresh(new_firmware_scamera)
    return {"success": True, "smart_camera_count": len(scameras)}


@router.get("/smartcamera/health_list", response_model=List[SmartCameraHealthList])
def get_health_smart_camera_lists(
    tenant_id: int,
    db: Session = Depends(get_pg_db),
    security_admin=Security(is_authenticated),
):
    url = "https://scamera.realsoft.ai/devices/getAllActiveDevices"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    all_active_devices: list = response.json()["devices"]
    devices = db_smartcamera.get_smart_cameras_for_health(db, tenant_id)
    result = []
    for device in devices:
        health_device = SmartCameraHealthList(**device.__dict__)
        health_device.status = "ONLINE" if device.device_id in all_active_devices else "OFFLINE"
        result.append(health_device)
    return result


@router.get("/smartcamera/not_created_list", response_model=List[SmartCameraNotCreated])
def get_not_created_smart_cameras(
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    redis_client=Depends(get_redis_connection),
):
    connected_smart_cameras = get_from_redis(redis_client, "connected_scameras")
    url = "https://scamera.realsoft.ai/devices/getAllActiveDevices"
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    all_active_devices: list = response.json()["devices"]
    result = []
    for active_device_id in all_active_devices:
        if active_device_id in connected_smart_cameras:
            camera_in_db = db.query(SmartCamera).filter_by(device_id=active_device_id, is_active=True).first()
            if not camera_in_db:
                found_camera = connected_smart_cameras[active_device_id]
                result.append(
                    {
                        "device_id": active_device_id,
                        "device_mac": found_camera["device_mac"],
                        "lib_platform_version": found_camera["lib_platform_version"],
                        "software_version": found_camera["software_version"],
                        "lib_ai_version": found_camera["lib_ai_version"],
                        "device_ip": found_camera["device_ip"],
                        "device_name": found_camera["device_name"],
                    }
                )
    return result


@router.get("/smartcamera/get_wired_network")
def get_wired_network(
    smart_camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = (
        f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getWiredNetwork"
        f"?password={smart_camera.password}"
    )
    response = requests.get(
        url,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    try:
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/smartcamera/set_wired_network")
def set_wired_network(
    smart_camera_id: int,
    data: SetWiredNetworkScheme,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setWiredNetwork"
    payload_dict = {
        "password": smart_camera.password,
        "DHCP": data.DHCP,
        "IP": data.IP,
        "subnet_mask": data.subnet_mask,
        "gateway": data.gateway,
        "manual_dns": data.manual_dns,
        "DNS": data.DNS,
        "DNS2": data.DNS2,
        "device_mac": data.device_mac,
        "webPort": data.webPort,
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
            return {
                "success": True,
                "message": "Smart Camera has been set Wired Network configurations successfully",
            }
        return HTTPException(status_code=400, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/smartcamera/get_platform_server")
def get_platform_server(
    smart_camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = (
        f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getPlatformServer"
        f"?password={smart_camera.password}"
    )
    response = requests.get(
        url,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    try:
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/smartcamera/set_platform_server")
def set_platform_server(
    smart_camera_id: int,
    data: SetPlatformServerScheme,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    if len(data.serverAddr) < 13 or not data.serverAddr.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="serverAddr must be https://serverAddr:port"
        )
    if len(data.wsServerAddr) < 10 or not data.wsServerAddr.startswith("ws://"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="wsServerAddr must be ws://serverAddr:port")
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setPlatformServer"
    payload_dict = {
        "password": smart_camera.password,
        "serverAddr": data.serverAddr,
        "wsServerAddr": data.wsServerAddr,
        "platformSubCode": data.platformSubCode,
        "resumeTransf": data.resumeTransf,
        "wsServerPort": data.wsServerPort,
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
            return {
                "success": True,
                "message": "Smart Camera has been set Platform Server configurations successfully",
            }
        return HTTPException(status_code=400, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/smartcamera/get_vpn_conf")
def get_vpn_conf(
    smart_camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = (
        f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getVPNConf"
        f"?password={smart_camera.password}"
    )
    response = requests.get(
        url,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    try:
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/smartcamera/set_vpn_conf")
def set_vpn_conf(
    smart_camera_id: int,
    data: SetVPNConfScheme,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setVPNConf"
    payload_dict = {
        "password": smart_camera.password,
        "enable": data.enable,
        "ipAddr": data.ip_address,
        "userName": data.vpn_username,
        "vpn_password": data.vpn_password,
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
            return {
                "success": True,
                "message": "Smart Camera has been set VPN configurations successfully",
            }
        return HTTPException(status_code=400, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/smartcamera/get_reboot_conf")
def get_reboot_conf(
    smart_camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = (
        f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getRebootConf"
        f"?password={smart_camera.password}"
    )
    response = requests.get(
        url,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    try:
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/smartcamera/set_reboot_conf")
def set_reboot_conf(
    smart_camera_id: int,
    data: SetRebootConfScheme,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setRebootConf"
    payload_dict = {
        "password": smart_camera.password,
        "day_week": data.day_week,
        "hour": data.hour,
        "minute": data.minute,
        "mode": data.mode,
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
            return {
                "success": True,
                "message": "Smart Camera has been set Reboot configurations successfully",
            }
        return HTTPException(status_code=400, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/smartcamera/get_face_config")
def get_face_config(
    smart_camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getFaceConfig"
    payload_dict = {"password": smart_camera.password}
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    try:
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post("/smartcamera/set_face_config")
def set_face_config(
    smart_camera_id: int,
    data: SetFaceConfigData,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/SetFaceConfig"
    payload_dict = {
        "password": smart_camera.password,
        "FaceQuality": data.FaceQuality,
        "FaceTrackTnable": data.FaceTrackTnable,
        "MaskDetectEnable": data.MaskDetectEnable,
        "FaceMiniPixel": data.FaceMiniPixel,
        "FaceMaxPixel": data.FaceMaxPixel,
        "DaEnable": data.DaEnable,
        "DetectAreaX": data.DetectAreaX,
        "DetectAreaY": data.DetectAreaY,
        "DetectAreaW": data.DetectAreaW,
        "DetectAreaH": data.DetectAreaH,
        "LivenessEnable": data.LivenessEnable,
        "LivenessThreshold": data.LivenessThreshold,
        "SnapMode": data.SnapMode,
        "IntervalFrame": data.IntervalFrame,
        "IntervalTime": data.IntervalTime,
        "SnapNum": data.SnapNum,
        "UploadMode": data.UploadMode,
        "ChooseMode": data.ChooseMode,
        "Yaw": data.Yaw,
        "Pitch": data.Pitch,
        "Roll": data.Roll,
        "FacePicQuality": data.FacePicQuality,
        "PicQuality": data.PicQuality,
        "SnapFaceArea": data.SnapFaceArea,
        "MultiFace": data.MultiFace,
        "BodyQuality": data.BodyQuality,
        "BodyAreaEx": data.BodyAreaEx,
        "ExposureMode": data.ExposureMode,
        "PicUploadMode": data.PicUploadMode,
        "WedIrMinFace": data.WedIrMinFace,
        "TempEnable": data.TempEnable,
        "CompEnable": data.CompEnable,
        "CmpThreshold": data.CmpThreshold,
        "IoType": data.IoType,
        "IOOutputTime": data.IOOutputTime,
        "AlarmTempValue": data.AlarmTempValue,
        "TempDetectAreaX": data.TempDetectAreaX,
        "TempDetectAreaY": data.TempDetectAreaY,
        "TempDetectAreaW": data.TempDetectAreaW,
        "TempDetectAreaH": data.TempDetectAreaH,
        "TempMinPixel": data.TempMinPixel,
        "TempMaxPixel": data.TempMaxPixel,
        "IoEnable": data.IoEnable,
        "ShowFaceName_N": data.ShowFaceName_N,
        "IoController": data.IoController,
        "TempType": data.TempType,
        "strangerFilt": data.strangerFilt,
        "strangerDay": data.strangerDay,
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
            return {
                "success": True,
                "message": "Smart Camera has been set face config successfully",
            }
        return HTTPException(status_code=400, detail=get_main_error_text(response))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.get("/smartcamera/rtmp_enable/{pk}")
async def rtmp_enable_or_disable_smart_camera(
    pk: int,
    enable: Optional[bool] = Query(default=True, alias="enable"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    def get_response_text() -> str:
        return "Enabled" if enable else "Disabled"

    smart_camera = db_smartcamera.get_smart_camera(db, pk, tenant_admin.tenant_id)
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
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
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_smartcamera.get_snapshots(db, camera_id, tenant_admin.tenant_id, limit)
    return paginate(query_set)


@router.get("/smartcamera/snapshot/{pk}", response_model=SmartCameraSnapshotFullInDB)
def get_smart_camera_snapshot(
    pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    snapshot = db.query(SmartCameraSnapshot).filter_by(id=pk, is_active=True).first()
    if not snapshot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not found")
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


@router.get("/smartcamera/realtime/snapshot/{pk}", response_model=SmartCameraSnapshotInDB)
def get_smart_camera_snapshot_realtime(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    smart_camera = db.query(SmartCamera).filter_by(id=pk, tenant_id=tenant_admin.tenant_id, is_active=True).first()
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
    if not minio_client.bucket_exists(SNAPSHOT_SCAMERA_BUCKET):
        minio_client.make_bucket(SNAPSHOT_SCAMERA_BUCKET)
    minio_client.put_object(
        SNAPSHOT_SCAMERA_BUCKET,
        file_name,
        image,
        response.json()["image_length"],
    )
    photo_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{SNAPSHOT_SCAMERA_BUCKET}/{file_name}"
    new_snapshot = SmartCameraSnapshot(
        smart_camera_id=smart_camera.id, snapshot_url=photo_url, tenant_id=smart_camera.tenant_id
    )
    db.add(new_snapshot)
    db.commit()
    db.refresh(new_snapshot)

    smart_camera.last_snapshot_url = photo_url
    db.commit()

    return new_snapshot


@timeit
def call_ptz_control(device_id: str, password: str, command: int) -> Response:
    url = f"http://{CAMERA_MANAGER_URL}/device/{device_id}/equipment/setPtzControl"
    payload_dict = {
        "password": password,
        "speed_h": 0,
        "speed_v": 0,
        "channel": 0,
        "ptz_cmd": command,
    }
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    return response


zoom_type_description = """
```
"zoom_type": str = ['in', 'out']
```
"""


@router.get("/smartcamera/zoom/{pk}", description=zoom_type_description)
def smart_camera_zoom(
    pk: int,
    zoom_type: str,  # ['in', 'out']
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    def change_cmd(command: int) -> int:
        return 10 if command == 9 else 9

    if zoom_type.lower() not in ["in", "out"]:
        raise HTTPException(status_code=400, detail='Zoom type must be "in" or "out"')
    smartcamera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not smartcamera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    cmd = 9 if zoom_type.lower() == "in" else 10
    zoom_response = call_ptz_control(smartcamera.device_id, smartcamera.password, command=cmd)
    if zoom_response.status_code == 200:
        zoom_response = zoom_response.json()
        if zoom_response["code"] == 0:
            time.sleep(1)
            call_ptz_control(smartcamera.device_id, smartcamera.password, command=21)  # to stop
            url = f"http://{CAMERA_MANAGER_URL}/device/{smartcamera.device_id}/equipment/getFmtSnap"
            payload_dict = {"password": smartcamera.password, "fmt": 0}
            payload = json.dumps(payload_dict)
            response = requests.post(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
            )
            if response.status_code == 200 and response.json()["code"] == 0:
                image_base64 = response.json()["image_base64"]
                image = io.BytesIO(base64.b64decode(image_base64))
                file_name = f"{uuid.uuid4()}.jpeg"
                if not minio_client.bucket_exists(SNAPSHOT_SCAMERA_BUCKET):
                    minio_client.make_bucket(SNAPSHOT_SCAMERA_BUCKET)
                minio_client.put_object(
                    SNAPSHOT_SCAMERA_BUCKET,
                    file_name,
                    image,
                    response.json()["image_length"],
                )
                photo_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{SNAPSHOT_SCAMERA_BUCKET}/{file_name}"
                new_snapshot = SmartCameraSnapshot(
                    smart_camera_id=smartcamera.id,
                    snapshot_url=photo_url,
                    tenant_id=smartcamera.tenant_id,
                )
                db.add(new_snapshot)
                db.commit()
                db.refresh(new_snapshot)

                smartcamera.last_snapshot_url = photo_url
                db.commit()

                return {"success": True, "image_url": photo_url}
            call_ptz_control(smartcamera.device_id, smartcamera.password, command=change_cmd(cmd))
            time.sleep(1)
            call_ptz_control(smartcamera.device_id, smartcamera.password, command=21)  # to stop
            raise HTTPException(status_code=response.status_code, detail=response.text)
        raise HTTPException(status_code=400, detail=f"Failed to Zoom in. code: {zoom_response['code']}")
    raise HTTPException(status_code=zoom_response.status_code, detail=zoom_response.text)


@router.get("/smartcamera/restart/{pk}")
def restart_smart_camera(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    new_task = SmartCameraTask(task_type="restart", smart_camera_id=smart_camera.id)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return {"success": True, "message": "Task created to restart smart camera."}


@router.get("/smartcamera/disk_format/{pk}")
def disk_format(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=404, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/diskFormat"
    payload_dict = {"password": smart_camera.password}
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
            return {"success": True, "message": "Successfully disk formatted"}
        return {"success": False, "message": response.text, "code": response.json()["code"]}
    except Exception as e:
        raise HTTPException(status_code=response.status_code, detail=response.text) from e


@router.get("/smartcamera/analytics/{pk}")
async def get_smart_camera_live_analytics(
    pk: int,
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    mongo_db=Depends(get_mongo_db),
    redis_client=Depends(get_redis_connection),
):
    smart_camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    cache_param = f"{date.year}:{date.month}:{date.day}"
    cache_key = f"s_camera:{pk}:{cache_param}:analytics"
    cached_data = get_from_redis(redis_client, cache_key)
    if cached_data:
        return cached_data
    start_day, end_day = date, date + timedelta(days=1) - timedelta(seconds=1)
    query = {"id": smart_camera.id, "created_at": {"$gte": start_day, "$lt": end_day}}
    try:
        cursor = await mongo_db.analytics.aggregate(
            [
                {"$match": query},
                {
                    "$project": {
                        "hour": {"$hour": "$created_at"},
                        "minute": {
                            "$subtract": [{"$minute": "$created_at"}, {"$mod": [{"$minute": "$created_at"}, 30]}]
                        },
                    }
                },
                {
                    "$project": {
                        "time_interval": {
                            "$concat": [
                                {
                                    "$cond": [
                                        {"$lt": ["$hour", 10]},
                                        {"$concat": ["0", {"$toString": "$hour"}]},
                                        {"$toString": "$hour"},
                                    ]
                                },
                                ":",
                                {"$cond": [{"$eq": ["$minute", 0]}, "00", "30"]},
                            ]
                        }
                    }
                },
                {"$group": {"_id": "$time_interval", "count": {"$sum": 1}}},
                {"$sort": {"_id": ASCENDING}},  # Optional: Sort results by time interval
            ]
        ).to_list(None)
    except Exception as e:
        return {"success": False, "error": str(e)}
    set_to_redis(redis_client, cache_key, cursor)
    return {"success": True, "data": cursor}


@router.get("/smartcamera/visitor/attendances", response_model=CustomPage[VisitorAttendanceInDB])
def smart_camera_visitor_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_smartcamera.get_user_attendances(db, "visitor", smart_camera_id, limit)
    return paginate(query_set)


@router.get("/smartcamera/identity/attendances", response_model=CustomPage[AttendanceInDB])
def smart_camera_identity_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_smartcamera.get_user_attendances(db, "identity", smart_camera_id, limit)
    return paginate(query_set)


@router.get("/smartcamera/wanted/attendances", response_model=CustomPage[WantedAttendanceInDB])
def smart_camera_wanted_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_smartcamera.get_user_attendances(db, "wanted", smart_camera_id, limit)
    return paginate(query_set)


def prettify_log(text: str) -> str:
    log_lines = text.split("</br>")
    pretty_log = []
    for line in log_lines:
        clean_line = line.strip()
        if not clean_line:
            continue
        pretty_log.append(clean_line)
    return "\n".join(pretty_log)


@router.get("/smartcamera/log_file")
def get_log_file(
    smart_camera_id: int,
    log_name: str,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    if len(log_name) < 5 and not log_name.endswith(".log"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect log name")
    smart_camera = (
        db.query(SmartCamera).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/getLogFile"
    payload_dict = {"password": smart_camera.password, "log_name": log_name}
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
            pretty_log = prettify_log(response.json()["log_info"])
            return {"success": True, "log": pretty_log}
        return {"success": False, "message": response.text, "code": response.json()["code"]}
    except Exception as e:
        raise HTTPException(status_code=response.status_code, detail=response.text) from e


@router.get("/smartcamera/suggested_password")
async def get_suggested_password():
    return await generate_password()


@router.get("/smartcamera/update/password/{pk}", response_model=SmartCameraInDB)
def update_password(
    pk: int,
    new_password: str,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    if smart_camera.tenant_id != tenant_admin.tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/equipment/setPassword"
    payload_dict = {"old_password": smart_camera.password, "new_password": new_password}
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
            smart_camera.password = new_password
            db.commit()
            db.refresh(smart_camera)
            return smart_camera
        raise HTTPException(status_code=400, detail=response.text)
    except Exception as e:
        raise HTTPException(status_code=response.status_code, detail=response.text) from e


def custom_paginate_for_smart_camera(db: Session, data: list, page: int, size: int):
    today = datetime.now().date()
    if not data:
        return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}
    total = len(data)
    pages = ceil(len(data) / size)
    wanted_data = data[(page - 1) * size : page * size]
    for item in wanted_data:
        attendance_count = (
            db.query(func.count(distinct(Attendance.identity_id)))
            .filter(
                and_(
                    Attendance.smart_camera_id == item.id,
                    Attendance.attendance_datetime >= today,
                    Attendance.attendance_datetime < today + timedelta(days=1),
                    Attendance.by_mobile.is_(False),
                    Attendance.mismatch_entity.is_(False),
                    Attendance.is_active,
                )
            )
            .scalar()
        )
        avagare_attendance_comp_score = (
            db.query(func.avg(Attendance.comp_score))
            .filter(
                and_(
                    Attendance.smart_camera_id == item.id,
                    Attendance.attendance_datetime >= today,
                    Attendance.attendance_datetime < today + timedelta(days=1),
                    Attendance.by_mobile.is_(False),
                    Attendance.mismatch_entity.is_(False),
                    Attendance.smart_camera_id.is_not(None),
                    Attendance.is_active,
                )
            )
            .scalar()
        )
        item.attendance_count = attendance_count
        item.avagare_attendance_comp_score = (
            float(f"{avagare_attendance_comp_score:.3f}") if avagare_attendance_comp_score else None
        )
    return {"items": wanted_data, "total": total, "page": page, "size": size, "pages": pages}


@router.get("/smartcamera", response_model=CustomPaginatedResponseForSmartCamera)
def get_smart_cameras(
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    room_id: Optional[int] = None,
    tenant_entity_id: Optional[int] = None,
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query = (
        db.query(SmartCamera)
        .join(TenantEntity, TenantEntity.id == SmartCamera.tenant_entity_id)
        .filter(and_(TenantEntity.tenant_id == tenant_admin.tenant_id, TenantEntity.is_active, SmartCamera.is_active))
    )

    if room_id is not None:
        query = query.filter(SmartCamera.room_id == room_id)

    if tenant_entity_id is not None:
        query = query.filter(SmartCamera.tenant_entity_id == tenant_entity_id)

    if district_id is not None:
        query = query.filter(TenantEntity.district_id == district_id)

    if region_id is not None:
        query = query.filter(TenantEntity.region_id == region_id)

    query = query.order_by(SmartCamera.id)

    data = query.all()

    return custom_paginate_for_smart_camera(db, data, page, size)


@router.get("/smartcamera/identity/attendance/analytics", response_model=IdentityAttendanceAnalyticsForSmartCamera)
def get_smart_camera_identity_attendance_analytics(
    smart_camera_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    smart_camera = (
        db.query(SmartCamera.id).filter_by(id=smart_camera_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera not found")
    uploaded_identities_count = (
        db.query(IdentitySmartCamera).filter_by(smart_camera_id=smart_camera_id, is_active=True).count()
    )
    today = datetime.today()
    daily_attendances_count = (
        db.query(Attendance.id)
        .filter(
            and_(
                Attendance.smart_camera_id == smart_camera_id,
                Attendance.by_mobile.is_(False),
                Attendance.attendance_datetime >= today,
                Attendance.attendance_datetime < today + timedelta(days=1),
                Attendance.smart_camera_id.is_not(None),
                Attendance.identity_id.is_not(None),
                Attendance.mismatch_entity.is_not(True),
            )
        )
        .group_by(Attendance.identity_id)
        .count()
    )
    return {"uploaded_identity_count": uploaded_identities_count, "daily_attendance_count": daily_attendances_count}


@router.get("/smartcamera/{pk}", response_model=SmartCameraInDB)
def get_smart_camera(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.get_smart_camera(db, pk, tenant_admin.tenant_id, is_active)


@router.post("/smartcamera", response_model=SmartCameraInDB)
async def create_smart_camera(
    smartcamera: SmartCameraBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    # new_password = await generate_password()
    # url = f"http://{CAMERA_MANAGER_URL}/device/{smartcamera.device_id}/equipment/setPassword"
    # payload_dict = {"old_password": smartcamera.password, "new_password": new_password}
    # payload = json.dumps(payload_dict)
    # response = requests.post(
    #     url,
    #     data=payload,
    #     headers={"Content-Type": "application/json"},
    #     auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    # )
    # smartcamera.password = "123456"
    # temp_password = None
    # try:
    #     response.raise_for_status()
    #     if response.json()["code"] == 0:
    #         smartcamera.password = new_password
    # except Exception as e:
    #     print(e)
    #     temp_password = new_password
    return db_smartcamera.create_smart_camera(db, smartcamera, tenant_admin.tenant_id, None)


@router.put("/smartcamera/{pk}", response_model=SmartCameraInDB)
def update_smart_camera(
    pk: int,
    smartcamera: SmartCameraBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.update_smart_camera(db, pk, smartcamera, tenant_admin.tenant_id)


@router.delete("/smartcamera/{pk}", response_model=SmartCameraInDB)
def delete_smart_camera(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.delete_smart_camera(db, pk)


@router.get("/smartcameras/for_map", response_model=List[SmartCameraForMap])
def get_smart_cameras_for_map(
    country_id: Optional[int] = None,
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_smartcamera.get_smart_cameras_for_map(
        db=db, tenant_id=tenant_admin.tenant_id, country_id=country_id, region_id=region_id, district_id=district_id
    )


@router.get("/jetson", response_model=CustomPage[JetsonInDB])
def get_jetson_devices(
    room_id: Optional[int] = Query(default=None, alias="room_id"),
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    # tenant_admin=Security(get_current_tenant_admin),
):
    # query_set = db_jetson.get_jetson_devices(db, tenant_admin.tenant_id, room_id, is_active)
    query_set = db_jetson.get_jetson_devices_unsafe(db, room_id, is_active)
    return paginate(query_set)


@router.get("/jetson/by_building/{id}")
def get_jetson_devices_by_building(
    id: int,
    is_active: bool = True,
    db: Session = Depends(get_pg_db),
):
    return db_jetson.get_jetson_device_by_building(db=db, building_id=id, is_active=is_active)


@router.get("/jetson/{pk}")
async def get_jetson_device(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    # tenant_admin=Security(get_current_tenant_admin),
    mongodb=Depends(get_logs_db),
):
    return await db_jetson.get_jetson_device(db, mongodb, pk, tenant_id=None, is_active=is_active)


@router.post("/jetson", response_model=JetsonInDB)
def create_jetson_device(
    jetson: JetsonBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.create_jetson_device(db, jetson, tenant_admin.tenant_id)


@router.put("/jetson/{pk}", response_model=JetsonInDB)
def update_jetson_device(
    pk: int,
    jetson: JetsonBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.update_jetson_device(db, pk, jetson, tenant_admin.tenant_id)


@router.delete("/jetson/{pk}", response_model=JetsonInDB)
def delete_jetson_device(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.delete_jetson_device(db, pk, tenant_admin.tenant_id)


@router.post("/jetson/setup_config")
def create_jetson_device_set_up_file(
    set_up_configs: JetsonDeviceSetUpConfigs,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    template = jinja_env.get_template("setup_payload/device_setup.sh")
    rendered_shell_script = template.render(
        github_token=set_up_configs.github_token,
        jetson_device_id=set_up_configs.jetson_device_id,
        jetson_device_manager_url=set_up_configs.jetson_device_manager_url,
    )

    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sh")
    with open(temporary_file.name, "w") as created_file:
        created_file.write(rendered_shell_script)

    return FileResponse(temporary_file.name, media_type="application/x-sh", filename="setup.sh")


@router.get("/jetson_device/cameras")
def get_jetson_device_cameras(
    pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_jetson.get_jetson_cameras(db=db, pk=pk)


@router.post("/jetson_profile")
def create_jetson_profile(
    jetson_profile_details: JetsonProfileCreate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.create_jetson_profile(
        db,
        jetson_profile_details.name,
        jetson_profile_details.username,
        jetson_profile_details.password,
        jetson_profile_details.cuda_version,
        jetson_profile_details.deepstream_version,
        jetson_profile_details.jetpack_version,
    )


@router.put("/jetson_profile/{pk}")
def update_jetson_profile(
    pk: int,
    jetson_optional_details: JetsonProfileUpdate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.update_jetson_profile(db, pk, jetson_optional_details)


@router.post("/jetson_profile/register_device")
def jetson_profile_register_device(
    data: JetsonProfileRegisterDevice,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.jetson_profile_register_device(db, data.jetson_profile_id, data.jetson_device_id)


@router.get("/jetson_profile/by_profile/{pk}")
def get_jetson_profile_by_profile(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.get_jetson_profile_by_profile(db, profile_id=pk)


@router.get("/jetson_profile/all", response_model=CustomPage[JetsonProfileInDB])
def get_jetson_profiles(db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    query_set = db_jetson.get_jetson_profiles(db)
    return paginate(query_set)


@router.get("/jetson_profile/by_device/{pk}")
def get_jetson_profile_by_device(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.get_jetson_profile_by_device(db, device_id=pk)


@router.delete("/jetson_profile/{pk}")
def delete_jetson_profile(
    pk: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_jetson.delete_jetson_profile(db=db, jetson_profile_id=pk)


@router.get("/jetson_device_stream/{pk}")
def get_jetson_stream(pk: int, db: Session = Depends(get_pg_db)):
    current_jetson_device = db_jetson.get_jetson_device_for_stream(db=db, pk=pk)

    if not current_jetson_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device stream is not found or inactive"
        )

    hls_stream_response = requests.post(
        HLS_CONVERTOR_PATH,
        params={
            "rtsp_url": f"rtsp://{current_jetson_device.device_ip_vpn}:8554/ds-test",
            "alias": current_jetson_device.device_name,
        },
    )

    if hls_stream_response.ok and hls_stream_response.json() and hls_stream_response.json().get("id"):
        return f"https://hls.realsoft.ai/stream/{hls_stream_response.json()['id']}/index.m3u8"

    print(hls_stream_response.json())

    return None
