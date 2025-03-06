from datetime import datetime
from typing import List, Optional, Union

import pytz
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from auth.oauth2 import get_current_tenant_admin
from database.database import get_one_system_mongo_db

router = APIRouter(prefix="/activity-logs", tags=["activity_logs"])


class ActivityLog(BaseModel):
    id: str
    response_status_code: Optional[int] = None
    request_path: Optional[str] = None
    request_method: Optional[str] = None
    request_time: datetime
    response_time: Optional[datetime] = None
    taken_time: Optional[float] = None
    request_body: Optional[Union[dict, str]] = None
    response_body: Optional[Union[dict, str]] = None
    request_query_params: Optional[dict] = None
    request_headers: Optional[dict] = None
    response_headers: Optional[dict] = None
    username: Optional[str] = None


class ActivityLogSchema(BaseModel):
    total: int
    items: List[ActivityLog]


class RequestPathsSchema(BaseModel):
    paths: List[str]


@router.get("/", response_model=ActivityLogSchema)
async def get_activity_logs(
    search: Optional[str] = Query(None, description="Search term for username (case-insensitive)"),
    response_status_code: Optional[int] = Query(None, description="Filter by HTTP response status code"),
    request_path: Optional[str] = Query(None, description="Filter by request path"),
    request_method: Optional[str] = Query(None, description="Filter by HTTP request method (e.g., GET, POST)"),
    request_time_start: Optional[datetime] = Query(None, description="Start datetime (YYYY-MM-DD)"),
    request_time_end: Optional[datetime] = Query(None, description="End datetime (YYYY-MM-DD)"),
    username: Optional[str] = Query(None, description="Filter by exact username"),
    limit: int = Query(25, ge=1, le=100, description="Number of logs to return (max 100)"),
    offset: int = Query(0, ge=0, description="Number of logs to skip for pagination"),
    tenant_admin=Depends(get_current_tenant_admin),
    mongo_client=Depends(get_one_system_mongo_db),
):
    query = {}

    filters = []
    if username:
        filters.append({"username": username})
    if search:
        filters.append({"username": {"$regex": search, "$options": "i"}})
    if filters:
        query["$or"] = filters

    if response_status_code is not None:
        query["response_status_code"] = response_status_code
    if request_path:
        query["request_path"] = request_path
    if request_method:
        query["request_method"] = request_method

    if request_time_start or request_time_end:
        query["request_time"] = {}
        if request_time_start:
            query["request_time"]["$gte"] = request_time_start.replace(hour=0, minute=0, second=0, tzinfo=pytz.UTC)
        if request_time_end:
            query["request_time"]["$lte"] = request_time_end.replace(hour=23, minute=59, second=59, tzinfo=pytz.UTC)

    total = await mongo_client["http_logs"].count_documents(query)

    cursor = mongo_client["http_logs"].find(query).sort("request_time", -1).skip(offset).limit(limit)
    activity_logs = [ActivityLog(**{**log, "id": str(log["_id"])}) async for log in cursor]

    return {"total": total, "items": activity_logs}


@router.get("/paths", response_model=RequestPathsSchema)
async def get_request_paths(
    tenant_admin=Depends(get_current_tenant_admin),
    mongo_client=Depends(get_one_system_mongo_db),
):
    pipeline = [{"$group": {"_id": "$request_path"}}, {"$sort": {"_id": 1}}]

    results = await mongo_client["http_logs"].aggregate(pipeline).to_list(length=None)

    paths = [result["_id"] for result in results if result["_id"]]

    return {"paths": paths}
