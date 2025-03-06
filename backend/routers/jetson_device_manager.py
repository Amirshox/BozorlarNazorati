import base64
import io
import os
import uuid

import requests
from fastapi import APIRouter, Depends, HTTPException, Security, status
from sqlalchemy.orm.session import Session

from auth.oauth2 import get_current_tenant_admin
from database.database import get_pg_db
from database.minio_client import get_minio_client
from models import Camera, CameraSnapshot
from models.nvdsanalytics import Roi
from schemas.jetson_device_manager import (
    AddDeepstreamApplicationRequest,
    ConfigUpdateAddGroup,
    ConfigUpdateAddProperty,
    ConfigUpdateRemoveGroup,
    ConfigUpdateRemoveProperty,
    ConfigUpdateReplaceProperty,
    EnlistApplicationConfigurations,
    EnlistDeepstreamApplication,
    GetCameras,
    GetNetworks,
    GetSnapshot,
    RunDeepstreamApplicationRequest,
    StopDeeepstreamApplicationRequest,
    UpdateDeepstreamAppCameras,
    UpdateDeepstreamAppLineCrossingStream,
    UpdateDeepstreamAppRequest,
    UpdateDeepstreamAppRoiStream,
)
from utils.log import timeit

JETSON_DEVICE_MANAGER_URL = "https://jetson-manager.realsoft.ai/jetson_device_manager/"
# JETSON_DEVICE_MANAGER_URL = "http://0.0.0.0:7777/jetson_device_manager/"
router = APIRouter(prefix="/jetson_device_manager", tags=["jetson_device_manager"])

BUCKET_NAME = "snapshot-scamera"
ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")


@router.post("/add_deepstream_app")
def add_deepstream_application(
    details: AddDeepstreamApplicationRequest, tenant_admin=Security(get_current_tenant_admin)
):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "add_deepstream_app", data=details.json()).json()


@router.post("/run_deepstream_app")
def run_deepstream_application(
    details: RunDeepstreamApplicationRequest, tenant_admin=Security(get_current_tenant_admin)
):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "run_deepstream_app", data=details.json()).json()


@router.post("/stop_deepstream_app")
def stop_deepstream_application(
    details: StopDeeepstreamApplicationRequest, tenant_admin=Security(get_current_tenant_admin)
):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "stop_deepstream_app", data=details.json()).json()


@router.post("/update_config/add_config_group")
def update_deepstream_app_config1(details: ConfigUpdateAddGroup, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "update_config/add_config_group", data=details.json()).json()


@router.post("/update_config/replace_config_group")
def update_deepstream_app_config2(details: ConfigUpdateAddGroup, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "update_config/replace_config_group", data=details.json()
    ).json()


@router.post("/update_config/remove_config_group")
def update_deepstream_app_config3(details: ConfigUpdateRemoveGroup, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "update_config/remove_config_group", data=details.json()
    ).json()


@router.post("/update_config/add_config_property")
def update_deepstream_app_config4(details: ConfigUpdateAddProperty, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "update_config/add_config_property", data=details.json()
    ).json()


@router.post("/update_config/replace_config_property")
def update_deepstream_app_config(details: ConfigUpdateReplaceProperty, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "update_config/replace_config_property", data=details.json()
    ).json()


@router.post("/update_config/remove_config_property")
def update_deepstream_app_config5(details: ConfigUpdateRemoveProperty, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "update_config/remove_config_property", data=details.json()
    ).json()


@router.post("/update_deepstream_app")
def update_deepstream_app(details: UpdateDeepstreamAppRequest, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "update_deepstream_app", data=details.json()).json()


@router.post("/enlist_deepstream_applications")
def enlist_deepstream_applications(
    details: EnlistDeepstreamApplication, tenant_admin=Security(get_current_tenant_admin)
):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "enlist_deepstream_applications", data=details.json()).json()


@router.post("/enlist_application_configurations")
def enlist_application_configurations(
    details: EnlistApplicationConfigurations, tenant_admin=Security(get_current_tenant_admin)
):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "enlist_application_configurations", data=details.json()
    ).json()


@router.post("/get_snapshot")
def get_snapshots(
    details: GetSnapshot,
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
    db: Session = Depends(get_pg_db),
):
    response = requests.post(url=JETSON_DEVICE_MANAGER_URL + "get_snapshot", data=details.json()).json()

    current_camera = db.query(Camera).filter_by(id=details.camera_id).first()

    if not current_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

    if response and response.get("snapshot"):
        image_data = base64.b64decode(response["snapshot"])

        if not minio_client.bucket_exists(BUCKET_NAME):
            minio_client.make_bucket(BUCKET_NAME)

        image_stream = io.BytesIO(image_data)
        object_name = "snap_" + str(uuid.uuid4())

        minio_client.put_object(
            bucket_name=BUCKET_NAME,
            object_name=f"{object_name}.jpg",
            data=image_stream,
            length=len(image_data),
            content_type="image/png",
        )

        minio_snapshot_url = f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_NAME}/{object_name}.jpg"

        camera_snapshot = CameraSnapshot(
            camera_id=current_camera.id,
            snapshot_url=minio_snapshot_url,
            snapshot_filename=object_name,
            snapshot_bucketname=BUCKET_NAME,
        )

        db.add(camera_snapshot)
        db.commit()
        db.refresh(camera_snapshot)

        return {"snapshot": minio_snapshot_url}
    return {"snapshot": None}


@router.get("/enlist_active_jetson_devices")
def enlist_active_jetson_devices(tenant_admin=Security(get_current_tenant_admin)):
    return requests.get(url=JETSON_DEVICE_MANAGER_URL + "enlist_active_jetson_devices").json()


@router.post("/enlist_active_cameras")
def enlist_active_cameras(details: GetCameras, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "enlist_active_cameras", data=details.json()).json()


@router.post("/enlist_network_interfaces")
def enlist_network_interfaces(details: GetNetworks, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(url=JETSON_DEVICE_MANAGER_URL + "enlist_network_interfaces", data=details.json()).json()


@router.post("/update_deepstream_app_cameras")
def update_deepstream_app_cameras(details: UpdateDeepstreamAppCameras, tenant_admin=Security(get_current_tenant_admin)):
    return requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "update_config/replace_config_group",
        json={
            "application_name": details.application_name,
            "application_version": details.application_version,
            "jetson_device_id": details.jetson_device_id,
            "config_file_name": "app_general_config",
            "config_group_name": "sources",
            "group_properties": details.camera_rtsp_urls,
        },
    ).json()


@router.post("/update_deepstream_app_roi_stream")
def update_deepstream_app_rois(
    details: UpdateDeepstreamAppRoiStream,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    response = requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "enlist_application_configurations",
        json={
            "application_name": details.application_name,
            "application_version": details.application_version,
            "jetson_device_id": details.jetson_device_id,
        },
    )

    if response.status_code == 200 and response.json():
        app_configurations = response.json()

        if not app_configurations.get("ds_nvds_analytics"):
            return {"status": "failed", "description": "Deepstram application does not support nvds analytics"}

        for each_group_name in app_configurations["ds_nvds_analytics"]:
            if each_group_name.startswith("roi"):
                requests.post(
                    url=JETSON_DEVICE_MANAGER_URL + "update_config/remove_config_group",
                    json={
                        "application_name": details.application_name,
                        "application_version": details.application_version,
                        "jetson_device_id": details.jetson_device_id,
                        "config_file_name": "ds_nvds_analytics",
                        "config_group_name": each_group_name,
                    },
                )

        for index, each_stream in enumerate(details.streams):
            rois = {}

            stream_class_id = 0

            for each_roi in each_stream.rois:
                rois[each_roi.roi_id] = each_roi.coordinates

            sample_roi = db.query(Roi).filter_by(id=each_stream.rois[0].roi_id).first()

            if sample_roi:
                if sample_roi.detection_object_type == "person":
                    stream_class_id = 0
                elif sample_roi.detection_object_type == "car":
                    stream_class_id = 2

            requests.post(
                url=JETSON_DEVICE_MANAGER_URL + "update_config/add_config_group",
                json={
                    "application_name": details.application_name,
                    "application_version": details.application_version,
                    "jetson_device_id": details.jetson_device_id,
                    "config_file_name": "ds_nvds_analytics",
                    "config_group_name": f"roi-filtering-stream-{index}",
                    "group_properties": {"class-id": stream_class_id, "enable": 1, "inverse-roi": 0, "rois": rois},
                },
            )

        return {"status": "succeded", "description": "Updated successfully"}
    return {"status": "failed", "description": "Failed to get deepstream app configurations"}


@router.post("/update_deepstream_app_line_stream")
def update_deepstream_app_lines(
    details: UpdateDeepstreamAppLineCrossingStream, tenant_admin=Security(get_current_tenant_admin)
):
    response = requests.post(
        url=JETSON_DEVICE_MANAGER_URL + "enlist_application_configurations",
        json={
            "application_name": details.application_name,
            "application_version": details.application_version,
            "jetson_device_id": details.jetson_device_id,
        },
    )

    if response.status_code == 200 and response.json():
        app_configurations = response.json()

        if not app_configurations.get("ds_nvds_analytics"):
            return {"status": "failed", "description": "Deepstram application does not support nvds analytics"}

        for each_group_name in app_configurations["ds_nvds_analytics"]:
            if each_group_name.startswith("line"):
                requests.post(
                    url=JETSON_DEVICE_MANAGER_URL + "update_config/remove_config_group",
                    json={
                        "application_name": details.application_name,
                        "application_version": details.application_version,
                        "jetson_device_id": details.jetson_device_id,
                        "config_file_name": "ds_nvds_analytics",
                        "config_group_name": each_group_name,
                    },
                )

        for index, each_stream in enumerate(details.streams):
            line_crossings = {}

            for each_line in each_stream.lines:
                line_crossings[each_line.line_id] = each_line.coordinates

            requests.post(
                url=JETSON_DEVICE_MANAGER_URL + "update_config/add_config_group",
                json={
                    "application_name": details.application_name,
                    "application_version": details.application_version,
                    "jetson_device_id": details.jetson_device_id,
                    "config_file_name": "ds_nvds_analytics",
                    "config_group_name": f"line-crossing-stream-{index}",
                    "group_properties": {"class-id": 0, "enable": 1, "extended": 0, "line-crossings": line_crossings},
                },
            )

            return {"status": "succeded", "description": "Updated successfully"}
    return {"status": "failed", "description": "Failed to get deepstream app configurations"}
