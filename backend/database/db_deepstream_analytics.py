import os
from datetime import datetime, timedelta
from typing import TypedDict

from minio import Minio
from minio.error import S3Error
from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
from sqlalchemy.orm import Session

from models import Identity

ENDPOINT = os.getenv("MINIO_ENDPOINT")
MINIO_PROTOCOL = os.getenv("MINIO_PROTOCOL")
MINIO_HOST = os.getenv("MINIO_HOST2")


def get_analytics_identity(db: Session, identity_id: int):
    return db.query(Identity).filter_by(id=identity_id).first()


class RoiAnalyticsReport(TypedDict):
    minutesInsideRoi: float
    minutesOutsideRoi: float


async def calculate_roi_analytics(
    roi_collection: AsyncIOMotorCollection, roi_id: int, analytics_date: datetime, jetson_device_id: str
):
    aggregation_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "@timestamp": {"$gte": analytics_date, "$lt": analytics_date + timedelta(days=1)},
                "roi_id": roi_id,
            }
        },
        {"$group": {"_id": "$roi_id", "events": {"$push": {"event_type": "$event_type", "timestamp": "$@timestamp"}}}},
        {
            "$project": {
                "durations": {
                    "$map": {
                        "input": {"$range": [0, {"$subtract": [{"$size": "$events"}, 1]}]},
                        "as": "idx",
                        "in": {
                            "start": {"$arrayElemAt": ["$events", "$$idx"]},
                            "end": {"$arrayElemAt": ["$events", {"$add": ["$$idx", 1]}]},
                        },
                    }
                }
            }
        },
        {"$unwind": "$durations"},
        {
            "$project": {
                "event_type": "$durations.start.event_type",
                "duration": {"$subtract": ["$durations.end.timestamp", "$durations.start.timestamp"]},
            }
        },
        {"$group": {"_id": "$event_type", "totalDuration": {"$sum": "$duration"}}},
        {"$project": {"_id": 0, "eventType": "$_id", "totalDurationInMinutes": {"$divide": ["$totalDuration", 60000]}}},
    ]

    aggregation_result = await roi_collection.aggregate(aggregation_pipeline).to_list(length=None)

    if aggregation_result:
        for each_report_field in aggregation_result:
            if each_report_field["eventType"] == "entrance":
                return each_report_field["totalDurationInMinutes"]
    return 0


async def calculate_roi_service_time(
    roi_collection: AsyncIOMotorCollection, roi_id: int, analytics_date: datetime, jetson_device_id: str
) -> float:
    aggregation_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "@timestamp": {"$gte": analytics_date, "$lt": analytics_date + timedelta(days=1)},
                "roi_id": roi_id,
            }
        },
        {"$group": {"_id": "$roi_id", "events": {"$push": {"event_type": "$event_type", "timestamp": "$@timestamp"}}}},
        {
            "$project": {
                "durations": {
                    "$map": {
                        "input": {"$range": [0, {"$subtract": [{"$size": "$events"}, 1]}]},
                        "as": "idx",
                        "in": {
                            "start": {"$arrayElemAt": ["$events", "$$idx"]},
                            "end": {"$arrayElemAt": ["$events", {"$add": ["$$idx", 1]}]},
                        },
                    }
                }
            }
        },
        {"$unwind": "$durations"},
        {
            "$project": {
                "event_type": "$durations.start.event_type",
                "duration": {"$subtract": ["$durations.end.timestamp", "$durations.start.timestamp"]},
            }
        },
        {"$group": {"_id": "$event_type", "totalDuration": {"$sum": "$duration"}}},
        {"$project": {"_id": 0, "eventType": "$_id", "totalDurationInMinutes": {"$divide": ["$totalDuration", 60000]}}},
    ]

    aggregation_result = await roi_collection.aggregate(aggregation_pipeline).to_list(length=None)

    if aggregation_result:
        for each_report_field in aggregation_result:
            if each_report_field["eventType"] == "entrance":
                return each_report_field["totalDurationInMinutes"]
    return 0


class RoiEntranceAnalyticsReport(TypedDict):
    roiFirstEntrance: datetime
    roiLastExit: datetime


async def calculate_roi_entrance_analytics(
    roi_collection: AsyncIOMotorCollection, roi_id: int, analytics_date: datetime, jetson_device_id: str
) -> RoiEntranceAnalyticsReport:
    first_entrance_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "event_type": "entrance",
                "@timestamp": {"$gte": analytics_date, "$lt": analytics_date + timedelta(days=1)},
                "roi_id": roi_id,
            }
        },
        {"$sort": {"@timestamp": 1}},
        {"$limit": 1},
    ]

    last_exit_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "event_type": "exit",
                "@timestamp": {"$gte": analytics_date, "$lt": analytics_date + timedelta(days=1)},
                "roi_id": roi_id,
            }
        },
        {"$sort": {"@timestamp": -1}},
        {"$limit": 1},
    ]

    first_entrance_aggregation_result = await roi_collection.aggregate(first_entrance_pipeline).to_list(length=None)
    last_exit_aggregation_result = await roi_collection.aggregate(last_exit_pipeline).to_list(length=None)

    return {
        "roiFirstEntrance": first_entrance_aggregation_result[0]["@timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        if first_entrance_aggregation_result
        else None,
        "roiLastExit": last_exit_aggregation_result[0]["@timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        if last_exit_aggregation_result
        else None,
    }


async def get_line_crossing_analytics(
    line_id: int,
    jetson_device_id: str,
    analytics_start_date: datetime,
    analytics_end_date: datetime,
    mongo_db: AsyncIOMotorDatabase,
    offset: int,
    limit: int,
):
    line_crossing_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "@timestamp": {
                    "$gte": analytics_start_date,
                    "$lt": analytics_start_date + timedelta(days=1)
                    if analytics_end_date is None
                    else analytics_end_date,
                },
                "line_id": line_id,
            }
        },
        {"$sort": {"@timestamp": 1}},
        {"$skip": offset},
        {"$limit": limit},
    ]

    return await mongo_db["line-crossing"].aggregate(line_crossing_pipeline).to_list(length=None)


async def get_work_analytics_report(
    roi_id: int, mongo_db: AsyncIOMotorDatabase, given_date: datetime, jetson_device_id: str
):
    report_details = {}
    specific_date = datetime.combine(given_date, datetime.min.time())

    roi_entrance_analytics = await calculate_roi_entrance_analytics(
        roi_collection=mongo_db["roi"], roi_id=roi_id, analytics_date=specific_date, jetson_device_id=jetson_device_id
    )

    roi_analytics = await calculate_roi_analytics(
        roi_collection=mongo_db["roi"], roi_id=roi_id, analytics_date=specific_date, jetson_device_id=jetson_device_id
    )

    service_time_analytics = await calculate_roi_service_time(
        roi_collection=mongo_db["roi"], roi_id=roi_id, analytics_date=specific_date, jetson_device_id=jetson_device_id
    )

    report_details["roiFirstEntrance"] = roi_entrance_analytics["roiFirstEntrance"]
    report_details["roiLastExit"] = roi_entrance_analytics["roiLastExit"]
    report_details["minutesWorkTime"] = roi_analytics
    report_details["minutesServiceTime"] = service_time_analytics

    return report_details


async def get_safe_zone_reports(
    roi_id: int,
    minio_client: Minio,
    mongo_db: AsyncIOMotorDatabase,
    safe_zone_start_time: datetime,
    safe_zone_end_time: datetime,
    jetson_device_id: str,
    bucket_name: str,
    offset: int,
    limit: int,
):
    safe_zone_entrances_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "event_type": "entrance",
                "@timestamp": {"$gte": safe_zone_start_time, "$lt": safe_zone_end_time},
                "roi_id": roi_id,
                "number_of_people": {"$gte": 1},
                "containsFrame": True,
            }
        },
        {"$sort": {"@timestamp": 1}},
        {"$skip": offset},
        {"$limit": limit},
    ]

    filtered_entrances = []
    entrances = await mongo_db["roi"].aggregate(safe_zone_entrances_pipeline).to_list(length=None)

    for each_entrance in entrances:
        try:
            minio_client.stat_object(bucket_name, each_entrance["event_id"] + ".jpg")
            is_frame_saved = True
        except S3Error:
            is_frame_saved = False

        if is_frame_saved:
            filtered_entrances.append(
                {
                    "entrance_time": each_entrance["@timestamp"],
                    "entrance_people_count": each_entrance["number_of_people"],
                    "entrance_frame_image": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{bucket_name}/{each_entrance['event_id']}.jpg",
                }
            )

    return filtered_entrances


async def get_overcrowd_reports(
    roi_id: int,
    minio_client: Minio,
    mongo_db: AsyncIOMotorDatabase,
    start_time: datetime,
    end_time: datetime,
    people_count_threshold: int,
    jetson_device_id: str,
    bucket_name: str,
    offset: int,
    limit: int,
):
    overcrowd_detection_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "event_type": "entrance",
                "@timestamp": {"$gte": start_time, "$lt": end_time},
                "roi_id": roi_id,
                "number_of_people": {"$gte": people_count_threshold},
                "containsFrame": True,
            }
        },
        {"$sort": {"@timestamp": 1}},
        {"$skip": offset},
        {"$limit": limit},
    ]

    filtered_overcrowd_detections = []
    overcrowd_detections = await mongo_db["roi"].aggregate(overcrowd_detection_pipeline).to_list(length=None)

    for each_detection in overcrowd_detections:
        try:
            minio_client.stat_object(bucket_name, each_detection["event_id"] + ".jpg")
            is_frame_saved = True
        except S3Error:
            is_frame_saved = False

        if is_frame_saved:
            filtered_overcrowd_detections.append(
                {
                    "overcrowd_time": each_detection["@timestamp"],
                    "overcrowd_people_count": each_detection["number_of_people"],
                    "overcrowd_frame_image": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{bucket_name}/{each_detection['event_id']}.jpg",
                }
            )

    return filtered_overcrowd_detections


async def illegal_parking_reports(
    roi_id: int,
    minio_client: Minio,
    mongo_db: AsyncIOMotorDatabase,
    start_time: datetime,
    end_time: datetime,
    jetson_device_id: str,
    bucket_name: str,
    offset: int,
    limit: int,
):
    illegal_parking_pipeline = [
        {
            "$match": {
                "jetson_device_id": jetson_device_id,
                "event_type": "car_parking",
                "@timestamp": {"$gte": start_time, "$lt": end_time},
                "roi_id": roi_id,
            }
        },
        {"$sort": {"@timestamp": 1}},
        {"$skip": offset},
        {"$limit": limit},
    ]

    filtered_illegal_parkings = []

    illegal_parkings = await mongo_db["roi"].aggregate(illegal_parking_pipeline).to_list(length=None)

    for each_detection in illegal_parkings:
        try:
            minio_client.stat_object(bucket_name, each_detection["event_id"] + ".jpg")
            is_frame_saved = True
        except S3Error:
            is_frame_saved = False

        if is_frame_saved:
            filtered_illegal_parkings.append(
                {
                    "parking_time": each_detection["@timestamp"],
                    "parking_image": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{bucket_name}/{each_detection['event_id']}.jpg",
                }
            )

    return filtered_illegal_parkings
