import asyncio
import base64
import io
import os
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Security, WebSocket, WebSocketDisconnect, status
from minio.error import S3Error
from motor.motor_asyncio import AsyncIOMotorDatabase
from sqlalchemy.orm import Session

from auth.oauth2 import get_tenant_entity_user
from database import db_deepstream_analytics, db_identity, db_jetson, nvdsanalytics
from database.database import get_mongo_db, get_pg_db
from database.minio_client import get_minio_client
from models import Camera, Identity, JetsonDevice, Line, Roi, RoiLabel
from schemas.nvdsanalytics import RawRoiAnalytics
from config import MINIO_PROTOCOL, MINIO_HOST

BUCKET_NAME = "deepstream-analytics"

router = APIRouter(prefix="/deepstream_analytics", tags=["deepstream_analytics"])

analytics_exchange = []


@router.post("/analytics_receiver", include_in_schema=False)
def event_consumer_analytics_receiver(
    request: Request,
    analytics: RawRoiAnalytics,
    db: Session = Depends(get_pg_db),
    minio_client=Depends(get_minio_client),
):
    current_roi = nvdsanalytics.get_roi(db=db, pk=analytics.roi_id)

    if current_roi:
        if analytics.illegal_parking:
            image_data = base64.b64decode(analytics.frame_image)

            if not minio_client.bucket_exists(BUCKET_NAME):
                minio_client.make_bucket(BUCKET_NAME)

            image_stream = io.BytesIO(image_data)

            minio_client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=f"{analytics.report_id}.jpg",
                data=image_stream,
                length=len(image_data),
                content_type="image/png",
            )

            return None

        for each_lable in current_roi.labels:
            current_time = datetime.strptime(analytics.timestamp, "%Y-%m-%d %H:%M:%S")
            current_camera = db.query(Camera).filter_by(id=current_roi.camera_id).first()
            current_camera_name: str = None

            if current_camera:
                current_camera_name = current_camera.name

            if each_lable.label_title == "safe-zone":
                safe_zone_start_time = datetime.combine(date.today(), current_roi.safe_zone_start_time)

                safe_zone_end_time = datetime.combine(date.today(), current_roi.safe_zone_end_time)

                if current_roi.safe_zone_start_time.hour >= current_roi.safe_zone_end_time.hour:
                    safe_zone_end_time = datetime.combine(
                        date.today() + timedelta(days=1), current_roi.safe_zone_start_time
                    )

                if safe_zone_start_time <= current_time <= safe_zone_end_time:
                    if analytics.frame_image:
                        image_data = base64.b64decode(analytics.frame_image)

                        if not minio_client.bucket_exists(BUCKET_NAME):
                            minio_client.make_bucket(BUCKET_NAME)

                        image_stream = io.BytesIO(image_data)

                        minio_client.put_object(
                            bucket_name=BUCKET_NAME,
                            object_name=f"{analytics.report_id}.jpg",
                            data=image_stream,
                            length=len(image_data),
                            content_type="image/png",
                        )

                    analytics_exchange.append(
                        {
                            "report_id": analytics.report_id,
                            "notification_type": "safe-zone",
                            "roi_id": analytics.roi_id,
                            "timestamp": analytics.timestamp,
                            "jetson_device_id": analytics.jetson_device_id,
                            "camera_name": current_camera_name,
                        }
                    )
            elif each_lable.label_title == "overcrowd-detection":
                if analytics.frame_image:
                    image_data = base64.b64decode(analytics.frame_image)

                    if not minio_client.bucket_exists(BUCKET_NAME):
                        minio_client.make_bucket(BUCKET_NAME)

                    image_stream = io.BytesIO(image_data)

                    minio_client.put_object(
                        bucket_name=BUCKET_NAME,
                        object_name=f"{analytics.report_id}.jpg",
                        data=image_stream,
                        length=len(image_data),
                        content_type="image/png",
                    )

                if analytics.number_of_people > current_roi.people_count_threshold:
                    analytics_exchange.append(
                        {
                            "report_id": analytics.report_id,
                            "notification_type": "overcrowd-detection",
                            "roi_id": analytics.roi_id,
                            "timestamp": analytics.timestamp,
                            "jetson_device_id": analytics.jetson_device_id,
                            "camera_name": current_camera_name,
                        }
                    )


def handle_notification_messages(jetson_device_id: str):
    for index, each_exchange in enumerate(analytics_exchange):
        if each_exchange["jetson_device_id"] == jetson_device_id:
            analytics_exchange.pop(index)
            return each_exchange

    return None


@router.websocket("/notification_center/{jetson_device_id}")
async def websocket_endpoint(jetson_device_id: str, websocket: WebSocket, minio_client=Depends(get_minio_client)):
    await websocket.accept()
    try:
        while True:
            current_notification = handle_notification_messages(jetson_device_id)

            if current_notification:
                try:
                    current_frame_image = (
                        f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_NAME}/{current_notification['report_id']}.jpg"
                    )
                    current_notification["frame_image"] = current_frame_image
                except S3Error:
                    current_notification["frame_image"] = None
                await websocket.send_json(current_notification)

            await asyncio.sleep(10)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"notification_center, websocket error: {e}")


@router.get("/line_crossing/daily_report")
async def daily_line_crossing_history(
    jetson_device_id: int,
    limit: int,
    offset: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    user=Security(get_tenant_entity_user),
):
    current_date = start_period
    current_jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    camera_lines = []

    jetson_device_cameras = db.query(Camera).filter_by(jetson_device_id=current_jetson_device.id).all()

    for each_camera in jetson_device_cameras:
        current_camera_lines = db.query(Line).filter_by(camera_id=each_camera.id).all()

        camera_lines.extend(current_camera_lines)

    final_reports = []

    while current_date <= end_period:
        for each_camera_line in camera_lines:
            crossings = []

            line_crossings = await db_deepstream_analytics.get_line_crossing_analytics(
                line_id=each_camera_line.id,
                jetson_device_id=current_jetson_device.device_id,
                analytics_start_date=datetime.combine(current_date, datetime.min.time()),
                analytics_end_date=None,
                offset=offset,
                limit=limit,
                mongo_db=mongo_db,
            )

            for each_line_crossing in line_crossings:
                crossings.append(each_line_crossing["@timestamp"])

            final_reports.append({"line": each_camera_line, "crossings": crossings, "date": current_date})

        current_date += timedelta(days=1)

    return final_reports


@router.get("/line_crossing/summary_report")
async def summary_line_crossing_history(
    jetson_device_id: int,
    limit: int,
    offset: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    user=Security(get_tenant_entity_user),
):
    current_jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    camera_lines = []

    jetson_device_cameras = db.query(Camera).filter_by(jetson_device_id=current_jetson_device.id).all()

    for each_camera in jetson_device_cameras:
        current_camera_lines = db.query(Line).filter_by(camera_id=each_camera.id).all()

        camera_lines.extend(current_camera_lines)

    final_reports = []

    for each_camera_line in camera_lines:
        crossings = []

        line_crossings = await db_deepstream_analytics.get_line_crossing_analytics(
            line_id=each_camera_line.id,
            jetson_device_id=current_jetson_device.device_id,
            analytics_start_date=datetime.combine(start_period, datetime.min.time()),
            analytics_end_date=datetime.combine(end_period, datetime.min.time()),
            offset=offset,
            limit=limit,
            mongo_db=mongo_db,
        )

        for each_line_crossing in line_crossings:
            crossings.append(each_line_crossing["@timestamp"])

        final_reports.append({"line": each_camera_line, "crossings": crossings})

    return final_reports


@router.get("/analytics_history/daily_report")
async def analytics_history(
    jetson_device_id: int,
    alarm_category: Literal["safe-zone", "overcrowd"],
    limit: int,
    offset: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    minio_client=Depends(get_minio_client),
    user=Security(get_tenant_entity_user),
):
    current_date = start_period

    current_jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    camera_rois = []

    jetson_device_cameras = db.query(Camera).filter_by(jetson_device_id=current_jetson_device.id).all()

    for each_camera in jetson_device_cameras:
        current_camera_rois = db.query(Roi).filter_by(camera_id=each_camera.id).all()

        camera_rois.extend(current_camera_rois)

    final_reports = []

    while current_date <= end_period:
        for each_camera_roi in camera_rois:
            current_reports = []

            if alarm_category == "safe-zone":
                if (not each_camera_roi.safe_zone_start_time) or (not each_camera_roi.safe_zone_end_time):
                    continue

                current_reports = await db_deepstream_analytics.get_safe_zone_reports(
                    roi_id=each_camera_roi.id,
                    mongo_db=mongo_db,
                    safe_zone_start_time=datetime.combine(current_date, each_camera_roi.safe_zone_start_time),
                    safe_zone_end_time=datetime.combine(current_date, each_camera_roi.safe_zone_end_time),
                    jetson_device_id=current_jetson_device.device_id,
                    minio_client=minio_client,
                    bucket_name=BUCKET_NAME,
                    limit=limit,
                    offset=offset,
                )
            elif alarm_category == "overcrowd":
                if not each_camera_roi.people_count_threshold:
                    continue

                current_reports = await db_deepstream_analytics.get_overcrowd_reports(
                    roi_id=each_camera_roi.id,
                    mongo_db=mongo_db,
                    start_time=datetime.combine(current_date, time(0, 0, 0)),
                    end_time=datetime.combine(current_date, time(23, 59, 59)),
                    jetson_device_id=current_jetson_device.device_id,
                    people_count_threshold=each_camera_roi.people_count_threshold,
                    minio_client=minio_client,
                    bucket_name=BUCKET_NAME,
                    limit=limit,
                    offset=offset,
                )

            if current_reports:
                final_reports.append({"roi": each_camera_roi, "reports": current_reports, "date": current_date})

        current_date += timedelta(days=1)

    return final_reports


# @router.get("/work_space/daily_report")
async def __DEPRECATED_work_analytics_report_daily(
    jetson_device_id: str,
    identity_id: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    user=Security(get_tenant_entity_user),
):
    current_date = start_period
    identity_rois = nvdsanalytics.get_identity_rois(db=db, identity_id=identity_id, roi_lable="work-analytics")
    analytics_reports = []

    while current_date <= end_period:
        for each_roi in identity_rois:
            current_report = {}

            current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                roi_id=each_roi.id, mongo_db=mongo_db, given_date=current_date, jetson_device_id=jetson_device_id
            )

            current_report["analytics"] = current_analytics
            current_report["roi"] = each_roi
            current_report["date"] = current_date

            analytics_reports.append(current_report)

        current_date += timedelta(days=1)

    return {
        "identity": db_deepstream_analytics.get_analytics_identity(db=db, identity_id=identity_id),
        "analytics_report": analytics_reports,
    }


# @router.get("/work_space/summary_report")
async def __DEPREACATED_work_analytics_report(
    jetson_device_id: str,
    identity_id: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    user=Security(get_tenant_entity_user),
):
    identity_rois = nvdsanalytics.get_identity_rois(db=db, identity_id=identity_id, roi_lable="work-analytics")
    current_date = start_period
    analytics_report = {}

    while current_date <= end_period:
        for each_roi in identity_rois:
            if not analytics_report.get(each_roi.id):
                analytics_report[each_roi.id] = {"minutesWorkTime": 0, "minutesServiceTime": 0}

            current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                roi_id=each_roi.id, mongo_db=mongo_db, given_date=current_date, jetson_device_id=jetson_device_id
            )

            analytics_report[each_roi.id] = {
                "minutesWorkTime": analytics_report[each_roi.id]["minutesWorkTime"]
                + current_analytics["minutesWorkTime"],
                "minutesServiceTime": analytics_report[each_roi.id]["minutesServiceTime"]
                + current_analytics["minutesServiceTime"],
            }

        current_date += timedelta(days=1)

    analytics_report_as_list = []

    for each_roi in identity_rois:
        analytics_report_as_list.append(
            {
                "analytics": {
                    "minutesWorkTime": analytics_report[each_roi.id]["minutesWorkTime"],
                    "minutesServiceTime": analytics_report[each_roi.id]["minutesServiceTime"],
                },
                "roi": each_roi,
            }
        )

    return {
        "identity": db_deepstream_analytics.get_analytics_identity(db=db, identity_id=identity_id),
        "analytics_report": analytics_report_as_list,
    }


# @router.get("/work_space/daily_report/all")
async def __DEPRECATED_work_analytics_report_all(
    jetson_device_id: str,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    offset: int = 0,
    limit: int = 0,
    user=Security(get_tenant_entity_user),
):
    all_reports = []
    current_jetson_device = db_jetson.get_jetson_device_by_id(db=db, device_id=jetson_device_id)

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found!")

    identities = (
        db_identity.get_identieis_by_jetson_id(db=db, jetson_device_id=current_jetson_device.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    for each_identity in identities:
        current_analytics_report = []
        current_date = start_period
        identity_rois = nvdsanalytics.get_identity_rois(db=db, identity_id=each_identity.id, roi_lable="work-analytics")

        while current_date <= end_period:
            for each_roi in identity_rois:
                current_report = {}

                current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                    roi_id=each_roi.id, mongo_db=mongo_db, given_date=current_date, jetson_device_id=jetson_device_id
                )

                current_report["analytics"] = current_analytics
                current_report["roi"] = each_roi
                current_report["date"] = current_date

                current_analytics_report.append(current_report)

            current_date += timedelta(days=1)

        all_reports.append({"identity": each_identity, "analytics_report": current_analytics_report})

    return all_reports


@router.get("/work_space/daily_report")
async def daily_work_analytics_report(
    identity_id: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    user=Security(get_tenant_entity_user),
):
    current_date = start_period
    current_identity = db.query(Identity).filter_by(id=identity_id).first()

    if not current_identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity does not exist")

    current_jetson_device = (
        db.query(JetsonDevice).filter_by(id=current_identity.jetson_device_id, is_active=True).first()
    )

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    identity_work_rois = (
        db.query(Roi).filter_by(identity_id=current_identity.id, workspace_type="worker", is_active=True).all()
    )

    identity_client_rois = (
        db.query(Roi).filter_by(identity_id=current_identity.id, workspace_type="client", is_active=True).all()
    )

    worker_analytics_reports = []
    client_analytics_reports = []

    while current_date <= end_period:
        for each_roi in identity_work_rois:
            current_report = {}

            current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                roi_id=each_roi.id,
                mongo_db=mongo_db,
                given_date=current_date,
                jetson_device_id=current_jetson_device.device_id,
            )

            current_report["analytics"] = current_analytics
            current_report["roi"] = each_roi
            current_report["date"] = current_date

            worker_analytics_reports.append(current_report)

        for each_roi in identity_client_rois:
            current_report = {}

            current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                roi_id=each_roi.id,
                mongo_db=mongo_db,
                given_date=current_date,
                jetson_device_id=current_jetson_device.device_id,
            )

            current_report["analytics"] = current_analytics
            current_report["roi"] = each_roi
            current_report["date"] = current_date

            client_analytics_reports.append(current_report)

        current_date += timedelta(days=1)

    analytics_report = []

    if not client_analytics_reports:
        for work_report in worker_analytics_reports:
            current_report = {
                "analytics": {
                    "roiFirstEntrance": work_report["analytics"]["roiFirstEntrance"],
                    "roiLastExit": work_report["analytics"]["roiLastExit"],
                    "minutesWorkTime": work_report["analytics"]["minutesWorkTime"],
                    "minutesServiceTime": 0,
                },
                "roi": work_report["roi"],
                "date": work_report["date"],
            }

            analytics_report.append(current_report)

        return analytics_report

    if not worker_analytics_reports:
        for service_report in client_analytics_reports:
            current_report = {
                "analytics": {
                    "roiFirstEntrance": service_report["analytics"]["roiFirstEntrance"],
                    "roiLastExit": service_report["analytics"]["roiLastExit"],
                    "minutesWorkTime": 0,
                    "minutesServiceTime": service_report["analytics"]["minutesWorkTime"],
                },
                "roi": service_report["roi"],
                "date": service_report["date"],
            }

            analytics_report.append(current_report)

        return analytics_report

    for work_report, service_report in zip(worker_analytics_reports, client_analytics_reports):
        current_report = {
            "analytics": {
                "roiFirstEntrance": work_report["analytics"]["roiFirstEntrance"],
                "roiLastExit": work_report["analytics"]["roiLastExit"],
                "minutesWorkTime": work_report["analytics"]["minutesWorkTime"],
                "minutesServiceTime": service_report["analytics"]["minutesWorkTime"],
            },
            "roi": work_report["roi"],
            "date": work_report["date"],
        }

        analytics_report.append(current_report)

    return analytics_report


@router.get("/work_space/daily_report/all")
async def work_analytics_report_all(
    jetson_device_id: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    offset: int = 0,
    limit: int = 0,
    user=Security(get_tenant_entity_user),
):
    all_reports = []

    current_jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    identities = (
        db_identity.get_identieis_by_jetson_id(db=db, jetson_device_id=current_jetson_device.id)
        .offset(offset)
        .limit(limit)
        .all()
    )

    for each_identity in identities:
        identity_work_rois = db.query(Roi).filter_by(
            identity_id=each_identity.id, workspace_type="worker", is_active=True
        )

        identity_client_rois = db.query(Roi).filter_by(
            identity_id=each_identity.id, workspace_type="client", is_active=True
        )

        worker_analytics_reports = []
        client_analytics_reports = []

        current_date = start_period

        while current_date <= end_period:
            for each_roi in identity_work_rois:
                current_report = {}

                current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                    roi_id=each_roi.id,
                    mongo_db=mongo_db,
                    given_date=current_date,
                    jetson_device_id=current_jetson_device.device_id,
                )

                current_report["analytics"] = current_analytics
                current_report["roi"] = each_roi
                current_report["date"] = current_date

                worker_analytics_reports.append(current_report)

            for each_roi in identity_client_rois:
                current_report = {}

                current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                    roi_id=each_roi.id,
                    mongo_db=mongo_db,
                    given_date=current_date,
                    jetson_device_id=current_jetson_device.device_id,
                )

                current_report["analytics"] = current_analytics
                current_report["roi"] = each_roi
                current_report["date"] = current_date

                client_analytics_reports.append(current_report)

            current_date += timedelta(days=1)

        analytics_report = []

        if not client_analytics_reports:
            for work_report in worker_analytics_reports:
                current_report = {
                    "analytics": {
                        "roiFirstEntrance": work_report["analytics"]["roiFirstEntrance"],
                        "roiLastExit": work_report["analytics"]["roiLastExit"],
                        "minutesWorkTime": work_report["analytics"]["minutesWorkTime"],
                        "minutesServiceTime": 0,
                    },
                    "roi": work_report["roi"],
                    "date": work_report["date"],
                }

                analytics_report.append(current_report)

        if not worker_analytics_reports:
            for service_report in client_analytics_reports:
                current_report = {
                    "analytics": {
                        "roiFirstEntrance": service_report["analytics"]["roiFirstEntrance"],
                        "roiLastExit": service_report["analytics"]["roiLastExit"],
                        "minutesWorkTime": 0,
                        "minutesServiceTime": service_report["analytics"]["minutesWorkTime"],
                    },
                    "roi": service_report["roi"],
                    "date": service_report["date"],
                }

                analytics_report.append(current_report)

        for work_report, service_report in zip(worker_analytics_reports, client_analytics_reports):
            current_report = {
                "analytics": {
                    "roiFirstEntrance": work_report["analytics"]["roiFirstEntrance"],
                    "roiLastExit": work_report["analytics"]["roiLastExit"],
                    "minutesWorkTime": work_report["analytics"]["minutesWorkTime"],
                    "minutesServiceTime": service_report["analytics"]["minutesWorkTime"],
                },
                "roi": work_report["roi"],
                "date": work_report["date"],
            }

            analytics_report.append(current_report)

        all_reports.append({"identity": each_identity, "analytics_report": analytics_report})

    return all_reports


@router.get("/work_space/summary_report")
async def summary_work_analytics_report(
    identity_id: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    user=Security(get_tenant_entity_user),
):
    current_date = start_period
    current_identity = db.query(Identity).filter_by(id=identity_id).first()

    if not current_identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity does not exist")

    current_jetson_device = (
        db.query(JetsonDevice).filter_by(id=current_identity.jetson_device_id, is_active=True).first()
    )

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    identity_work_rois = (
        db.query(Roi).filter_by(identity_id=current_identity.id, workspace_type="worker", is_active=True).all()
    )

    identity_client_rois = (
        db.query(Roi).filter_by(identity_id=current_identity.id, workspace_type="client", is_active=True).all()
    )

    worker_analytics_reports = []
    client_analytics_reports = []

    while current_date <= end_period:
        for each_roi in identity_work_rois:
            current_report = {}

            current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                roi_id=each_roi.id,
                mongo_db=mongo_db,
                given_date=current_date,
                jetson_device_id=current_jetson_device.device_id,
            )

            current_report["analytics"] = current_analytics
            current_report["roi"] = each_roi.id
            current_report["date"] = current_date

            worker_analytics_reports.append(current_report)

        for each_roi in identity_client_rois:
            current_report = {}

            current_analytics = await db_deepstream_analytics.get_work_analytics_report(
                roi_id=each_roi.id,
                mongo_db=mongo_db,
                given_date=current_date,
                jetson_device_id=current_jetson_device.device_id,
            )

            current_report["analytics"] = current_analytics
            current_report["roi"] = each_roi.id
            current_report["date"] = current_date

            client_analytics_reports.append(current_report)

        current_date += timedelta(days=1)

    total_work_time = dict()

    for work_report in worker_analytics_reports:
        if total_work_time.get(work_report["roi"]):
            total_work_time[work_report["roi"]] += work_report["analytics"]["minutesWorkTime"]
        else:
            total_work_time[work_report["roi"]] = work_report["analytics"]["minutesWorkTime"]

    total_service_time = dict()

    for service_report in client_analytics_reports:
        if total_service_time.get(service_report["roi"]):
            total_service_time[service_report["roi"]] += service_report["analytics"]["minutesWorkTime"]
        else:
            total_service_time[service_report["roi"]] = service_report["analytics"]["minutesWorkTime"]

    final_reports = []

    for each_roi in identity_work_rois + identity_client_rois:
        if each_roi.workspace_type == "worker":
            final_reports.append({"roi": each_roi, "minutesInsideRoi": total_work_time[each_roi.id]})
        elif each_roi.workspace_type == "client":
            final_reports.append({"roi": each_roi, "minutesInsideRoi": total_service_time[each_roi.id]})

    return {"identity": current_identity, "analytics": final_reports}


@router.get("/illegal_parking/daily_report")
async def illegal_parking(
    jetson_device_id: int,
    limit: int,
    offset: int,
    db: Session = Depends(get_pg_db),
    mongo_db: AsyncIOMotorDatabase = Depends(get_mongo_db),
    start_period: date = datetime.now().strftime("%Y-%m-%d"),  # noqa
    end_period: date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),  # noqa
    minio_client=Depends(get_minio_client),
    # user=Security(get_tenant_entity_user),
):
    current_date = start_period
    current_jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not current_jetson_device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")

    jetson_device_cameras = db.query(Camera).filter_by(jetson_device_id=current_jetson_device.id)

    jetson_device_rois = []
    car_parking_rois = []

    for each_camera in jetson_device_cameras:
        current_camera_rois = db.query(Roi).filter_by(camera_id=each_camera.id)
        jetson_device_rois.extend(current_camera_rois)

    for each_roi in jetson_device_rois:
        current_roi_lable = db.query(RoiLabel).filter_by(roi_id=each_roi.id, label_title="car-parking").first()

        if current_roi_lable:
            car_parking_rois.append(each_roi)

    reports = []

    while current_date <= end_period:
        for each_car_parking_roi in car_parking_rois:
            current_report = {}

            parking_report = await db_deepstream_analytics.illegal_parking_reports(
                roi_id=each_car_parking_roi.id,
                minio_client=minio_client,
                mongo_db=mongo_db,
                offset=offset,
                limit=limit,
                start_time=datetime.combine(current_date, time(0, 0, 0)),
                end_time=datetime.combine(current_date, time(23, 59, 59)),
                jetson_device_id=current_jetson_device.device_id,
                bucket_name=BUCKET_NAME,
            )

            current_report["roi"] = each_car_parking_roi
            current_report["reports"] = parking_report
            current_report["date"] = current_date

            reports.append(current_report)

        current_date += timedelta(days=1)
    return reports
