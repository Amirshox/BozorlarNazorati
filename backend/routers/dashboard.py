from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from auth.oauth2 import get_tenant_entity_user
from database.database import get_mongo_db, get_pg_db
from models import SmartCamera, TenantEntity
from schemas.dashboard import (
    AgeGenderBreakdownSchema,
    DailyBreakdownSchema,
    HourlyBreakdownSchema,
    VisitsBreakdownSchema,
)
from schemas.tenant_hierarchy_entity import TenantEntityInDB

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def create_default_pipeline(device_ids, start_date, end_date):
    return [{"$match": {"capture_time": {"$gte": start_date, "$lte": end_date}, "device_id": {"$in": device_ids}}}]


def fetch_device_ids_for_tenant(db, entity_id: int):
    return [
        device.device_id
        for device in db.query(SmartCamera.device_id)
        .filter(and_(SmartCamera.tenant_entity_id == entity_id, SmartCamera.is_active))
        .all()
    ]


def separate_by_day(data, days_count: int) -> dict:
    result = {}
    for i in range(1, days_count + 1):
        result[i] = 0
    for _ in data:
        result[_["capture_time"].day] += 1
    return result


def separate_by_hour(data) -> dict:
    result = {5: 0, 7: 0, 8: 0, 9: 0, 10: 0, 12: 0, 13: 0, 14: 0, 16: 0, 17: 0, 18: 0, 20: 0, 24: 0}
    for _ in data:
        if _["capture_time"].hour < 5:
            result[5] += 1
        elif _["capture_time"].hour < 7:
            result[7] += 1
        elif _["capture_time"].hour < 8:
            result[8] += 1
        elif _["capture_time"].hour < 9:
            result[9] += 1
        elif _["capture_time"].hour < 10:
            result[10] += 1
        elif _["capture_time"].hour < 12:
            result[12] += 1
        elif _["capture_time"].hour < 13:
            result[13] += 1
        elif _["capture_time"].hour < 14:
            result[14] += 1
        elif _["capture_time"].hour < 16:
            result[16] += 1
        elif _["capture_time"].hour < 17:
            result[17] += 1
        elif _["capture_time"].hour < 18:
            result[18] += 1
        elif _["capture_time"].hour < 20:
            result[20] += 1
        else:
            result[24] += 1
    return result


def separate_by_age(data) -> dict:
    result = {
        "0-10": 0,
        "11-15": 0,
        "16-20": 0,
        "21-25": 0,
        "26-30": 0,
        "31-35": 0,
        "36-40": 0,
        "41-45": 0,
        "46-50": 0,
        "51-55": 0,
        "56-60": 0,
        "60+": 0,
    }
    for _ in data:
        if _["age"] < 11:
            result["0-10"] += 1
        elif _["age"] < 16:
            result["11-15"] += 1
        elif _["age"] < 21:
            result["16-20"] += 1
        elif _["age"] < 26:
            result["21-25"] += 1
        elif _["age"] < 31:
            result["26-30"] += 1
        elif _["age"] < 36:
            result["31-35"] += 1
        elif _["age"] < 41:
            result["36-40"] += 1
        elif _["age"] < 46:
            result["41-45"] += 1
        elif _["age"] < 51:
            result["46-50"] += 1
        elif _["age"] < 56:
            result["51-55"] += 1
        elif _["age"] < 61:
            result["56-60"] += 1
        else:
            result["60+"] += 1
    return result


def is_division_by_zero(main: int, second: int) -> int:
    try:
        return int(100 * (second - main) / main)
    except ZeroDivisionError:
        return 100


def compare_entities(data: dict, selected_id: int) -> dict:
    selected_entity = data[selected_id]
    for entity_id in data:
        if entity_id == selected_id:
            continue
        for key in data[entity_id].keys():  # noqa
            data[entity_id][key] = [
                data[entity_id][key],
                is_division_by_zero(selected_entity[key], data[entity_id][key]),
            ]
    return data


def compare_entities_by_total(data: dict, selected_id: int) -> dict:
    selected_entity = data[selected_id]
    result = {selected_id: len(selected_entity)}
    for entity_id in data:
        if entity_id == selected_id:
            continue
        result[entity_id] = [len(data[entity_id]), is_division_by_zero(len(selected_entity), len(data[entity_id]))]
    return result


async def get_default_mongo_data(mongo_client, device_ids: list, start: datetime, end: datetime) -> list:
    return await mongo_client.visitor_analytics.aggregate(create_default_pipeline(device_ids, start, end)).to_list(None)


async def get_entity_visitor_data(db, mongo_client, ids: list, date: datetime) -> list:
    def residual_days() -> int:
        if date.month in [1, 3, 5, 7, 8, 10, 12]:
            return 31 - date.day
        if date.month in [4, 6, 9, 11]:
            return 30 - date.day
        if date.year % 4 == 0 and date.month == 2:
            return 29 - date.day
        return 30 - date.day

    result = []
    start_day, end_day = date, date + timedelta(days=1) - timedelta(seconds=1)
    start_week, end_week = date - timedelta(days=6), date + timedelta(days=1) - timedelta(seconds=1)
    start_month, end_month = (
        date - timedelta(days=date.day),
        date + timedelta(days=residual_days()) - timedelta(seconds=1),
    )
    intervals = [[start_day, end_day], [start_week, end_week], [start_month, end_month]]
    for interval in intervals:
        data = {}
        for tenant_entity_id in ids:
            device_ids = fetch_device_ids_for_tenant(db, tenant_entity_id)
            entity_data = await get_default_mongo_data(mongo_client, device_ids, interval[0], interval[1])
            data[tenant_entity_id] = entity_data
        result.append(data)
    return result


def max_month_days(date: datetime) -> int:
    if date.month in [1, 3, 5, 7, 8, 10, 12]:
        return 31
    if date.month in [4, 6, 9, 11]:
        return 30
    if date.year % 4 == 0 and date.month == 2:
        return 29 - date.day
    return 28


@router.get("/tenant_entities/by_district", response_model=List[TenantEntityInDB])
async def get_entities_by_district(
    district_id: int, db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user)
):
    return (
        db.query(TenantEntity)
        .filter(
            and_(TenantEntity.district_id == district_id, TenantEntity.hierarchy_level == 3, TenantEntity.is_active)
        )
        .all()
    )


@router.post("/analytics/visitor_comparison")
async def compare_visits(
    tenant_entity_ids: List[int],
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    mongo_client=Depends(get_mongo_db),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    result = {"today": None, "week": None, "month": None, "by_age": None, "by_hour": None, "by_day": None}
    data = await get_entity_visitor_data(db, mongo_client, tenant_entity_ids, date)
    result["today"] = compare_entities_by_total(data[0], tenant_entity_ids[0])
    result["week"] = compare_entities_by_total(data[1], tenant_entity_ids[0])
    result["month"] = compare_entities_by_total(data[2], tenant_entity_ids[0])
    age_data = {}
    hourly_data = {}
    month_data = {}
    for entity_id in tenant_entity_ids:
        age_data[entity_id] = separate_by_age(data[0][entity_id])
        hourly_data[entity_id] = separate_by_hour(data[0][entity_id])
        month_data[entity_id] = separate_by_day(data[0][entity_id], max_month_days(date))
    result["by_age"] = compare_entities(data=age_data, selected_id=tenant_entity_ids[0])
    result["by_hour"] = compare_entities(data=hourly_data, selected_id=tenant_entity_ids[0])
    result["by_day"] = compare_entities(data=month_data, selected_id=tenant_entity_ids[0])
    return result


@router.get("/analytics/visits", response_model=VisitsBreakdownSchema)
async def get_visits(
    start_date: datetime = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: datetime = Query(..., description="End date in YYYY-MM-DD format"),
    tenant_entity_id: int = Query(None, description="Tenant Entity ID"),
    mongo_client=Depends(get_mongo_db),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    def reformat_period_stats(stats: list) -> dict:
        result = {}
        for stat in stats:
            if stat["_id"] == "male":
                result["male"] = stat["count"]
            elif stat["_id"] == "female":
                result["female"] = stat["count"]
            elif stat["_id"] == "undefined":
                result["undefined"] = stat["count"]
        for key in ["male", "female", "undefined"]:
            if key not in result:
                result[key] = 0
        return result

    if tenant_entity_id:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(or_(SmartCamera.tenant_entity_id == tenant_entity_id, TenantEntity.parent_id == tenant_entity_id))
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    else:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(
                or_(
                    SmartCamera.tenant_entity_id == user.tenant_entity_id,
                    TenantEntity.parent_id == user.tenant_entity_id,
                )
            )
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    smart_cameras = query.all()

    devices_id = [smart_camera.device_id for smart_camera in smart_cameras]

    try:
        # Adjust the start_date and end_date to include the entire day
        start_date = datetime(start_date.year, start_date.month, start_date.day)
        end_date = datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59)

        match_criteria = {"capture_time": {"$gte": start_date, "$lte": end_date}}
        if devices_id:
            match_criteria["device_id"] = {"$in": devices_id}

        current_period_pipeline = [
            {
                "$match": {"capture_time": {"$gte": start_date, "$lte": end_date}, "device_id": {"$in": devices_id}},
            },
            {"$group": {"_id": "$sex", "count": {"$sum": 1}}},
        ]
        current_period_stats = await mongo_client["visitor_analytics"].aggregate(current_period_pipeline).to_list(None)
        current_total = sum(stat["count"] for stat in current_period_stats)

        # Calculate stats for the previous period
        previous_period_length = end_date - start_date
        previous_start_date = start_date - previous_period_length
        previous_end_date = start_date

        previous_period_pipeline = [
            {
                "$match": {
                    "capture_time": {"$gte": previous_start_date, "$lt": previous_end_date},
                    "device_id": {"$in": devices_id},
                },
            },
            {"$group": {"_id": "$sex", "count": {"$sum": 1}}},
        ]
        previous_period_stats = (
            await mongo_client["visitor_analytics"].aggregate(previous_period_pipeline).to_list(None)
        )
        previous_total = sum(stat["count"] for stat in previous_period_stats)

        try:
            trend = round((current_total - previous_total) / previous_total * 100, 2)
        except ZeroDivisionError:
            trend = 0
        return {"total": current_total, "trend": trend, "gender": reformat_period_stats(current_period_stats)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/analytics/visits/daily-breakdown", response_model=list[DailyBreakdownSchema])
async def get_monthly_daily_breakdown(
    start_date: datetime = Query(..., description="Start date in YYYY-MM format"),
    end_date: datetime = Query(..., description="End date in YYYY-MM format"),
    tenant_entity_id: int = Query(None, description="Tenant Entity ID"),
    mongo_client=Depends(get_mongo_db),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    if tenant_entity_id:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(or_(SmartCamera.tenant_entity_id == tenant_entity_id, TenantEntity.parent_id == tenant_entity_id))
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    else:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(
                or_(
                    SmartCamera.tenant_entity_id == user.tenant_entity_id,
                    TenantEntity.parent_id == user.tenant_entity_id,
                )
            )
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    smart_cameras = query.all()

    devices_id = [smart_camera.device_id for smart_camera in smart_cameras]

    try:
        pipeline = [
            {"$match": {"capture_time": {"$gte": start_date, "$lt": end_date}, "device_id": {"$in": devices_id}}},
            {"$project": {"day": {"$dayOfMonth": "$capture_time"}, "sex": {"$ifNull": ["$sex", "undefined"]}}},
            {"$group": {"_id": {"day": "$day", "sex": "$sex"}, "count": {"$sum": 1}}},
            {"$group": {"_id": "$_id.day", "counts": {"$push": {"sex": "$_id.sex", "count": "$count"}}}},
            {"$sort": {"_id": 1}},
        ]
        results = await mongo_client["visitor_analytics"].aggregate(pipeline).to_list(None)

        # Transform results to required format
        formatted_results = [
            {"date": result["_id"], "counts": {count["sex"]: count["count"] for count in result["counts"]}}
            for result in results
        ]

        return formatted_results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/analytics/visits/hourly-breakdown", response_model=list[HourlyBreakdownSchema])
async def get_today_hourly_visits(
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    tenant_entity_id: int = Query(None, description="Tenant Entity ID"),
    mongo_client=Depends(get_mongo_db),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    if tenant_entity_id:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(or_(SmartCamera.tenant_entity_id == tenant_entity_id, TenantEntity.parent_id == tenant_entity_id))
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    else:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(
                or_(
                    SmartCamera.tenant_entity_id == user.tenant_entity_id,
                    TenantEntity.parent_id == user.tenant_entity_id,
                )
            )
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    smart_cameras = query.all()

    device_ids = [smart_camera.device_id for smart_camera in smart_cameras]

    try:
        start_of_today = datetime(date.year, date.month, date.day)
        end_of_today = start_of_today + timedelta(days=1)

        pipeline = [
            {
                "$match": {
                    "capture_time": {"$gte": start_of_today, "$lt": end_of_today},
                    "device_id": {"$in": device_ids},
                }
            },
            {"$project": {"hour": {"$hour": "$capture_time"}}},
            {"$group": {"_id": "$hour", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        results = await mongo_client["visitor_analytics"].aggregate(pipeline).to_list(None)

        # Format the results to fill in any missing hours with zero visitors
        hourly_counts = {result["_id"]: result["count"] for result in results}
        formatted_results = [{"hour": hour, "count": hourly_counts.get(hour, 0)} for hour in range(24)]

        return formatted_results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/analytics/visits/age-gender-breakdown", response_model=list[AgeGenderBreakdownSchema])
async def get_age_gender_breakdown(
    date: datetime = Query(..., description="Date in YYYY-MM-DD format"),
    tenant_entity_id: int = Query(None, description="Tenant Entity ID"),
    mongo_client=Depends(get_mongo_db),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    if tenant_entity_id:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(or_(SmartCamera.tenant_entity_id == tenant_entity_id, TenantEntity.parent_id == tenant_entity_id))
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    else:
        query = (
            db.query(SmartCamera)
            .join(TenantEntity, SmartCamera.tenant_entity_id == TenantEntity.id)
            .filter(
                or_(
                    SmartCamera.tenant_entity_id == user.tenant_entity_id,
                    TenantEntity.parent_id == user.tenant_entity_id,
                )
            )
            .filter(and_(SmartCamera.is_active, TenantEntity.is_active))
            .options(joinedload(SmartCamera.tenant_entity))
        )
    smart_cameras = query.all()

    device_ids = [smart_camera.device_id for smart_camera in smart_cameras]

    try:
        end_of_today = date + timedelta(days=1)

        pipeline = [
            {"$match": {"capture_time": {"$gte": date, "$lt": end_of_today}, "device_id": {"$in": device_ids}}},
            {
                "$bucket": {
                    "groupBy": "$age",
                    "boundaries": [0, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                    "default": "55+",
                    "output": {
                        "male": {"$sum": {"$cond": [{"$eq": ["$sex", "male"]}, 1, 0]}},
                        "female": {"$sum": {"$cond": [{"$eq": ["$sex", "female"]}, 1, 0]}},
                        "undefined": {"$sum": {"$cond": [{"$not": {"$in": ["$sex", ["male", "female"]]}}, 1, 0]}},
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ]
        results = await mongo_client["visitor_analytics"].aggregate(pipeline).to_list(None)

        # Define the boundaries for formatting age groups
        age_boundaries = [0, 15, 20, 25, 30, 35, 40, 45, 50, 55]
        formatted_results = []
        for index, result in enumerate(results):
            if index == len(age_boundaries) - 1:
                age_group = f"{age_boundaries[index]}+"
            else:
                age_group = f"{age_boundaries[index]}-{age_boundaries[index + 1] - 1}"

            formatted_result = {
                "age_group": age_group,
                "counts": {"male": result["male"], "female": result["female"], "undefined": result["undefined"]},
            }
            formatted_results.append(formatted_result)

        return formatted_results
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
