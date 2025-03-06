import contextlib
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from math import ceil
from typing import Any, List, Literal, Optional

import requests
from aio_pika.abc import AbstractRobustConnection
from fastapi import APIRouter, Depends, HTTPException, Query, Security, WebSocket, status
from fastapi_pagination import Page, Params
from fastapi_pagination import paginate as iterable_paginate
from fastapi_pagination.ext.sqlalchemy import paginate
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin
from database import db_relative, db_tenant_entity
from database.database import get_analytics_cache_db, get_pg_db, get_rabbitmq_connection
from database.db_smartcamera import create_task_to_scamera
from database.minio_client import get_minio_client
from models import (
    Attendance,
    District,
    Identity,
    IdentityRelative,
    IdentitySmartCamera,
    Module,
    Relative,
    RelativeAttendance,
    SimilarityMainPhotoInArea,
    SimilarityMainPhotoInEntity,
    SmartCamera,
    Tenant,
    TenantEntity,
    TenantProfile,
    TenantProfileModule,
    VisitorAttendance,
    Wanted,
    WantedAttendance,
)
from schemas.identity import RelativeBase, RelativeCreate, RelativeInDB
from schemas.shared import ModuleInDBBase
from schemas.tenant_hierarchy_entity import (
    EntityForFilter,
    MttCompareAttendanceCount,
    SimilarIdentityInAreaResponse,
    SimilarIdentityInEntityResponse,
    TenantEntityAttendanceAnalytics,
    TenantEntityCreate,
    TenantEntityCreateExternal,
    TenantEntityCreateListResponse,
    TenantEntityFilteredDetails,
    TenantEntityInDB,
    TenantEntityUpdate,
)
from tasks import (
    add_wanted_to_smart_camera,
    create_relative_identity_list_task,
    update_relative_photo_with_pinfl_task,
    upload_relative_with_task,
)
from utils.image_processing import get_image_from_query, make_minio_url_from_image
from utils.pagination import CustomPage

router = APIRouter(prefix="/tenant_entity", tags=["tenant_entity"])

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")
RELATIVE_IDENTITY_BUCKET = os.getenv("MINIO_RELATIVE_IDENTITY", "relative-identity")

NODAVLAT_BASE_URL = os.getenv("NODAVLAT_BASE_URL")
BASIC_AUTH = {"Authorization": "Basic cmVhbHNvZnRhaTpyZWFsc29mdGFpNDU2NSE="}

logger = logging.getLogger(__name__)


@router.get("/available/modules", response_model=List[ModuleInDBBase])
def get_tenant_available_modules(db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)):
    return (
        db.query(Module)
        .join(TenantProfileModule)
        .join(TenantProfile)
        .join(Tenant)
        .filter(Tenant.id == tenant_admin.tenant_id)
        .all()
    )


# @router.post("/sync/platon/{pk}")
# def sync_db_with_platon(
#     pk: int,
#     identity_group: int,
#     data: List[IdentityForSync],
#     tenant_admin=Depends(get_current_tenant_admin),
# ):
#     # if len(data) > 1500:
#     #     raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Data is no more than 1500 items")
#     # smart_cameras = (
#     #     db.query(SmartCamera).filter_by(tenant_id=tenant_admin.tenant_id, tenant_entity_id=pk, is_active=True).all()
#     # )
#     # if len(smart_cameras) == 0:
#     #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No smart cameras found")
#     serializable_data = []
#     for identity in data:
#         if identity.identity_group == identity_group:
#             item = {
#                 "id": identity.id,
#                 "first_name": identity.first_name,
#                 "last_name": identity.last_name,
#                 "photo": identity.photo,
#                 "email": identity.email,
#                 "phone": identity.phone,
#                 "pinfl": identity.pinfl,
#                 "identity_group": identity.identity_group,
#                 "identity_type": identity.identity_type,
#                 "external_id": identity.external_id,
#                 "group_id": identity.group_id,
#                 "group_name": identity.group_name,
#             }
#             serializable_data.append(item)
#     # for smart_camera in smart_cameras:
#     if not serializable_data:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No data received")
#     sync_with_platon_task.delay(pk, tenant_admin.tenant_id, serializable_data, identity_group)
#     # return {"smart_camera_count": len(smart_cameras)}
#     return {"success": True, "received_count": len(serializable_data)}


class PaginatedResponse(BaseModel):
    total_items: int
    page: int
    page_size: int
    total_pages: int
    data: List[MttCompareAttendanceCount]


@router.get("/mtt/analytics", response_model=PaginatedResponse)
def get_mtt_compare_attendance_count(
    visit_date: date = Query(..., alias="visit_date"),
    only_different: bool = Query(False, alias="only_different"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    district_id: Optional[int] = Query(None, alias="district_id"),
    mtt_id: Optional[int] = Query(None, alias="mtt_id"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Depends(get_current_tenant_admin),
):
    if mtt_id:
        entities = (
            db.query(TenantEntity).filter_by(external_id=mtt_id, tenant_id=tenant_admin.tenant_id, is_active=True).all()
        )
    elif district_id:
        entities = (
            db.query(TenantEntity.id, TenantEntity.external_id, TenantEntity.name)
            .filter_by(tenant_id=tenant_admin.tenant_id, district_id=district_id, hierarchy_level=3, is_active=True)
            .filter(TenantEntity.external_id.is_not(None))
            .all()
        )
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mtt_id or district_id is required")
    if not entities:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No entities found")
    mtt_ids = [str(entity.external_id) for entity in entities]
    params = {"mtt_id": f"{','.join(mtt_ids)},", "visit_date": visit_date.strftime("%Y-%m-%d")}
    r = requests.get(
        url=NODAVLAT_BASE_URL + "api/v1/realsoftai/mtt/visit/statistics", headers=BASIC_AUTH, params=params
    )
    if r.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=r.json()["message"])

    data = r.json()["data"]

    result = []
    for item_from_remote_api in data:
        mtt_id_str = str(item_from_remote_api["mtt_id"])
        if mtt_id_str not in mtt_ids:
            continue
        idx = mtt_ids.index(mtt_id_str)

        total_count = (
            db.query(Attendance.id)
            .filter(
                and_(
                    Attendance.tenant_entity_id == entities[idx].id,
                    Attendance.attendance_datetime >= visit_date,
                    Attendance.attendance_datetime < visit_date + timedelta(days=1),
                )
            )
            .distinct(Attendance.identity_id)
            .count()
        )
        if only_different and total_count == item_from_remote_api["total_kids"] + item_from_remote_api["total_edus"]:
            continue

        kids_count = (
            db.query(Attendance.id)
            .join(Identity, Identity.id == Attendance.identity_id)
            .filter(
                and_(
                    Attendance.tenant_entity_id == entities[idx].id,
                    Attendance.attendance_datetime >= visit_date,
                    Attendance.attendance_datetime < visit_date + timedelta(days=1),
                    Identity.identity_group == 0,
                )
            )
            .distinct(Attendance.identity_id)
            .count()
        )

        employees_count = (
            db.query(Attendance.id)
            .join(Identity, Identity.id == Attendance.identity_id)
            .filter(
                and_(
                    Attendance.tenant_entity_id == entities[idx].id,
                    Attendance.attendance_datetime >= visit_date,
                    Attendance.attendance_datetime < visit_date + timedelta(days=1),
                    Identity.identity_group == 1,
                )
            )
            .distinct(Attendance.identity_id)
            .count()
        )

        attendance_item = MttCompareAttendanceCount(
            id=entities[idx].id,
            mtt_id=item_from_remote_api["mtt_id"],
            name=entities[idx].name,
            total_count=total_count,
            kids_count=kids_count,
            employees_count=employees_count,
            total_kids=item_from_remote_api["total_kids"],
            accepted_kids=item_from_remote_api["accepted_kids"],
            rejected_kids=item_from_remote_api["rejected_kids"],
            waiting_kids=item_from_remote_api["waiting_kids"],
            total_edus=item_from_remote_api["total_edus"],
            accepted_edus=item_from_remote_api["accepted_edus"],
            rejected_edus=item_from_remote_api["rejected_edus"],
            waiting_edus=item_from_remote_api["waiting_edus"],
        )
        result.append(attendance_item)

    total_items = len(result)
    total_pages = ceil(total_items / page_size)

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    paginated_data = result[start_idx:end_idx]

    return PaginatedResponse(
        total_items=total_items,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        data=paginated_data,
    )


@router.get("/sync/scamera")
def sync_smart_camera(
    smart_camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
    url = f"http://{CAMERA_MANAGER_URL}/device/{smart_camera.device_id}/user_management/queryTheUserListInformation"
    payload_dict = {"password": smart_camera.password, "start": 0, "length": 0}
    payload = json.dumps(payload_dict)
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        auth=(CAMERA_MANAGER_BASIC, CAMERA_MANAGER_PASSWORD),
    )
    # response = {
    #     "user_id_list": [
    #         {"user_id": "14214"}
    #     ],
    #     "user_num": 1193,
    #     "resp_type": "getUserList",
    #     "request_id": "f47c",
    #     "code": 0,
    #     "device_mac": "bc-07-18-01-94-0d",
    #     "deviceID": "H010001180F0100010019",
    #     "device_id": "H010001180F0100010019",
    #     "log": "'getUserList' success",
    #     "device_ip": "192.168.100.195",
    #     "sign_tby": "0c802dee9da35e871e13f24e7b716f4a"
    # }
    if response.status_code == 200:
        response_data = response.json()
        if response_data["code"] == 0:
            only_identities = [
                int(_id["user_id"]) for _id in response_data["user_id_list"] if _id["user_id"][0].isdigit()
            ]
            for item in only_identities:
                exist_identity = (
                    db.query(IdentitySmartCamera)
                    .filter_by(smart_camera_id=smart_camera_id, identity_id=item, is_active=True)
                    .first()
                )
                if not exist_identity:
                    new_i_scamera = IdentitySmartCamera(smart_camera_id=smart_camera_id, identity_id=item)
                    db.add(new_i_scamera)
                    db.commit()
                    db.refresh(new_i_scamera)
            db_list = db.query(IdentitySmartCamera).filter_by(smart_camera_id=smart_camera_id, is_active=True).all()
            for item in db_list:
                if item.identity_id not in only_identities:
                    db.delete(item)
                    db.commit()
            new_db_list = db.query(IdentitySmartCamera).filter_by(smart_camera_id=smart_camera_id, is_active=True).all()
            return {
                "success": len(only_identities) == len(new_db_list),
                "smart_camera_id": smart_camera_id,
                "device_id": smart_camera.device_id,
            }
        else:
            return {
                "success": False,
                "smart_camera_id": smart_camera_id,
                "device_id": smart_camera.device_id,
                "code": response_data["code"],
            }
    else:
        return {
            "success": False,
            "smart_camera_id": smart_camera_id,
            "device_id": smart_camera.device_id,
            "error": response.text,
            "status_code": response.status_code,
        }


@router.get("/create_task_for_defect_identity_scameras", description="Sync identities amoung db_scameras")
def create_task_for_defect_identity_scameras(
    tenant_entity_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    big_data = []
    max_count = 0
    max_camera_id = 0
    result = []
    smart_cameras = db.query(SmartCamera).filter_by(tenant_entity_id=tenant_entity_id, is_active=True).all()
    if len(smart_cameras) > 1:
        max_data = []
        for smart_camera in smart_cameras:
            i_scameras = db.query(IdentitySmartCamera).filter_by(smart_camera_id=smart_camera.id, is_active=True).all()
            if len(i_scameras) > max_count:
                max_count = len(i_scameras)
            big_data.append({"id": smart_camera.id, "count": len(i_scameras), "data": i_scameras})
        if max_count:
            for scamera_data in big_data:
                if scamera_data["count"] == max_count:
                    max_camera_id = scamera_data["id"]
                    max_data = scamera_data["data"]
                    big_data.remove(scamera_data)
                    break
            for scamera_data in big_data:
                camera_result = {
                    "smart_camera_id": scamera_data["id"],
                    "count": scamera_data["count"],
                    "new_task_count": 0,
                }
                if scamera_data["count"] != max_count:
                    for item in max_data:
                        if (
                            not db.query(IdentitySmartCamera)
                            .filter_by(smart_camera_id=scamera_data["id"], identity_id=item.identity_id, is_active=True)
                            .first()
                        ):
                            create_task_to_scamera(db, "add", scamera_data["id"], item.identity_id, "identity")
                            camera_result["new_task_count"] += 1
                result.append(camera_result)
    return {
        "success": True,
        "smart_camera_count": len(smart_cameras),
        "max_count": max_count,
        "max_camera_id": max_camera_id,
        "result": result,
    }


@router.get("/similar/identities/in_entity", response_model=SimilarIdentityInEntityResponse)
def get_similar_identities_in_entity(
    tenant_entity_id: int | None = None,
    region_id: int | None = None,
    district_id: int | None = None,
    min_distance: float | None = 0.0,
    max_distance: float | None = 1.0,
    start_date: datetime = Query(..., alias="start_date"),
    end_date: datetime = Query(..., alias="end_date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    offset = (page - 1) * page_size

    count_entity_query = (
        db.query(Identity.id)
        .distinct()
        .join(SimilarityMainPhotoInEntity, SimilarityMainPhotoInEntity.identity_id == Identity.id)
        .join(TenantEntity, TenantEntity.id == Identity.tenant_entity_id)
        .filter(
            SimilarityMainPhotoInEntity.created_at >= start_date,
            SimilarityMainPhotoInEntity.created_at < end_date,
            SimilarityMainPhotoInEntity.is_active,
            Identity.is_active,
            TenantEntity.is_active,
            TenantEntity.tenant_id == tenant_admin.tenant_id,
        )
    )

    if tenant_entity_id:
        count_entity_query = count_entity_query.filter(Identity.tenant_entity_id == tenant_entity_id)
    elif district_id:
        count_entity_query = count_entity_query.filter(TenantEntity.district_id == district_id)
    elif region_id:
        count_entity_query = count_entity_query.filter(TenantEntity.region_id == region_id)

    if min_distance is not None and max_distance:
        count_entity_query = count_entity_query.filter(
            SimilarityMainPhotoInEntity.distance >= min_distance,
            SimilarityMainPhotoInEntity.distance <= max_distance,
        )
    entity_total = count_entity_query.count()
    entity_identity_ids = [_.id for _ in count_entity_query.offset(offset).limit(page_size).all()]

    entity_similarities_query = (
        db.query(
            SimilarityMainPhotoInEntity, Identity.first_name, Identity.last_name, Identity.pinfl, TenantEntity.name
        )
        .join(Identity, Identity.id == SimilarityMainPhotoInEntity.identity_id)
        .join(TenantEntity, TenantEntity.id == Identity.tenant_entity_id)
        .filter(
            and_(
                SimilarityMainPhotoInEntity.created_at >= start_date,
                SimilarityMainPhotoInEntity.created_at < end_date,
                SimilarityMainPhotoInEntity.is_active,
                Identity.is_active,
                TenantEntity.is_active,
                TenantEntity.tenant_id == tenant_admin.tenant_id,
                SimilarityMainPhotoInEntity.identity_id.in_(entity_identity_ids),
            )
        )
    )
    if min_distance is not None and max_distance:
        entity_similarities_query = entity_similarities_query.filter(
            SimilarityMainPhotoInEntity.distance >= min_distance,
            SimilarityMainPhotoInEntity.distance <= max_distance,
        )
    entity_similarities = entity_similarities_query.all()

    entity_result = defaultdict(lambda: {"items": []})
    for item in entity_similarities:
        new_item = item[0].__dict__.copy()
        new_item["first_name"] = item[1]
        new_item["last_name"] = item[2]
        new_item["pinfl"] = item[3]
        new_item["tenant_entity_name"] = item[4]

        identity_id = new_item["identity_id"]

        if not entity_result[identity_id].get("first_name"):
            entity_result[identity_id]["first_name"] = new_item["first_name"]
            entity_result[identity_id]["last_name"] = new_item["last_name"]
            entity_result[identity_id]["version"] = new_item["version"]
            entity_result[identity_id]["pinfl"] = new_item["pinfl"]
            entity_result[identity_id]["image_url"] = new_item["image_url"]
            entity_result[identity_id]["tenant_entity_id"] = new_item["tenant_entity_id"]
            entity_result[identity_id]["tenant_entity_name"] = new_item["tenant_entity_name"]

        similar_entity = None
        similar_identity = (
            db.query(Identity.first_name, Identity.last_name, Identity.tenant_entity_id)
            .filter_by(id=item[0].similar_identity_id, is_active=True)
            .first()
        )
        if similar_identity:
            similar_entity = (
                db.query(TenantEntity.name).filter_by(id=similar_identity.tenant_entity_id, is_active=True).first()
            )

        entity_result[identity_id]["items"].append(
            {
                "id": new_item["id"],
                "similar_identity_id": new_item["similar_identity_id"],
                "similar_identity_first_name": similar_identity.first_name if similar_identity else "inactive",
                "similar_identity_last_name": similar_identity.last_name if similar_identity else "inactive",
                "similar_tenant_entity_id": new_item["similar_tenant_entity_id"],
                "similar_entity_name": similar_entity.name if similar_entity else "inactive",
                "similar_version": new_item["similar_version"],
                "distance": new_item["distance"],
                "similar_image_url": new_item["similar_image_url"],
                "created_at": new_item["created_at"],
            }
        )

    entity_result = [
        {
            "identity_id": identity_id,
            "first_name": details["first_name"],
            "last_name": details["last_name"],
            "version": details["version"],
            "pinfl": details["pinfl"],
            "image_url": details["image_url"],
            "tenant_entity_id": details["tenant_entity_id"],
            "tenant_entity_name": details["tenant_entity_name"],
            "similarities": details["items"],
        }
        for identity_id, details in entity_result.items()
    ]

    return {"items": entity_result, "total": entity_total, "page": page, "size": page_size}


@router.get("/similar/identities/in_area", response_model=SimilarIdentityInAreaResponse)
def get_similar_identities_in_area(
    tenant_entity_id: int | None = None,
    region_id: int | None = None,
    district_id: int | None = None,
    min_distance: float | None = 0.0,
    max_distance: float | None = 1.0,
    start_date: datetime = Query(..., alias="start_date"),
    end_date: datetime = Query(..., alias="end_date"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    offset = (page - 1) * page_size

    count_area_query = (
        db.query(Identity.id)
        .distinct()
        .join(SimilarityMainPhotoInArea, SimilarityMainPhotoInArea.identity_id == Identity.id)
        .join(TenantEntity, TenantEntity.id == Identity.tenant_entity_id)
        .filter(
            SimilarityMainPhotoInArea.created_at >= start_date,
            SimilarityMainPhotoInArea.created_at < end_date,
            SimilarityMainPhotoInArea.is_active,
            Identity.is_active,
            TenantEntity.is_active,
            TenantEntity.tenant_id == tenant_admin.tenant_id,
        )
    )

    if tenant_entity_id:
        count_area_query = count_area_query.filter(Identity.tenant_entity_id == tenant_entity_id)
    elif district_id:
        count_area_query = count_area_query.filter(TenantEntity.district_id == district_id)
    elif region_id:
        count_area_query = count_area_query.filter(TenantEntity.region_id == region_id)

    if min_distance is not None and max_distance:
        count_area_query = count_area_query.filter(
            SimilarityMainPhotoInArea.distance >= min_distance,
            SimilarityMainPhotoInArea.distance <= max_distance,
        )
    area_total = count_area_query.count()
    area_identity_ids = [_.id for _ in count_area_query.offset(offset).limit(page_size).all()]

    area_similarities_query = (
        db.query(SimilarityMainPhotoInArea, Identity.first_name, Identity.last_name, Identity.pinfl, TenantEntity.name)
        .join(Identity, Identity.id == SimilarityMainPhotoInArea.identity_id)
        .join(TenantEntity, TenantEntity.id == Identity.tenant_entity_id)
        .filter(
            and_(
                SimilarityMainPhotoInArea.created_at >= start_date,
                SimilarityMainPhotoInArea.created_at < end_date,
                SimilarityMainPhotoInArea.is_active,
                Identity.is_active,
                TenantEntity.is_active,
                TenantEntity.tenant_id == tenant_admin.tenant_id,
                SimilarityMainPhotoInArea.identity_id.in_(area_identity_ids),
            )
        )
    )
    if min_distance is not None and max_distance:
        area_similarities_query = area_similarities_query.filter(
            SimilarityMainPhotoInArea.distance >= min_distance,
            SimilarityMainPhotoInArea.distance <= max_distance,
        )
    area_similarities = area_similarities_query.all()

    area_result = defaultdict(lambda: {"items": []})
    for item in area_similarities:
        new_item = item[0].__dict__.copy()
        new_item["first_name"] = item[1]
        new_item["last_name"] = item[2]
        new_item["pinfl"] = item[3]
        new_item["tenant_entity_name"] = item[4]

        identity_id = new_item["identity_id"]

        if not area_result[identity_id].get("first_name"):
            area_result[identity_id]["first_name"] = new_item["first_name"]
            area_result[identity_id]["last_name"] = new_item["last_name"]
            area_result[identity_id]["version"] = new_item["version"]
            area_result[identity_id]["pinfl"] = new_item["pinfl"]
            area_result[identity_id]["image_url"] = new_item["image_url"]
            area_result[identity_id]["tenant_entity_name"] = new_item["tenant_entity_name"]

        similar_entity = None
        similar_identity = (
            db.query(Identity.first_name, Identity.last_name, Identity.tenant_entity_id)
            .filter_by(id=item[0].similar_identity_id, is_active=True)
            .first()
        )
        if similar_identity:
            similar_entity = (
                db.query(TenantEntity.name).filter_by(id=similar_identity.tenant_entity_id, is_active=True).first()
            )

        area_result[identity_id]["items"].append(
            {
                "id": new_item["id"],
                "similar_identity_id": new_item["similar_identity_id"],
                "similar_identity_first_name": similar_identity.first_name if similar_identity else "inactive",
                "similar_identity_last_name": similar_identity.last_name if similar_identity else "inactive",
                "similar_tenant_entity_id": similar_identity.tenant_entity_id if similar_identity else None,
                "similar_entity_name": similar_entity.name if similar_entity else "inactive",
                "similar_version": new_item["similar_version"],
                "distance": new_item["distance"],
                "updated_at": new_item["updated_at"],
                "similar_image_url": new_item["similar_image_url"],
                "created_at": new_item["created_at"],
            }
        )

    area_result = [
        {
            "identity_id": identity_id,
            "first_name": details["first_name"],
            "last_name": details["last_name"],
            "version": details["version"],
            "pinfl": details["pinfl"],
            "image_url": details["image_url"],
            "tenant_entity_name": details["tenant_entity_name"],
            "similarities": details["items"],
        }
        for identity_id, details in area_result.items()
    ]

    return {"items": area_result, "total": area_total, "page": page, "size": page_size}


@router.post("/add_wanteds")
def add_wanteds_to_tenant_entity(
    tenant_entity_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    wanteds = db.query(Wanted).filter_by(is_active=True).all()
    if not wanteds:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wanted not found")
    smart_cameras = (
        db.query(SmartCamera)
        .filter_by(tenant_id=tenant_admin.tenant_id, tenant_entity_id=tenant_entity_id, is_active=True)
        .all()
    )
    if not smart_cameras:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Smart camera not found")
    try:
        for smart_camera in smart_cameras:
            for wanted in wanteds:
                add_wanted_to_smart_camera.delay(
                    wanted.id,
                    wanted.first_name,
                    wanted.photo,
                    wanted.concern_level,
                    wanted.accusation,
                    smart_camera.id,
                    smart_camera.device_id,
                    smart_camera.password,
                    tenant_admin.tenant_id,
                    tenant_entity_id,
                )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Add wanted to camera delay error: {e}"
        ) from e
    return {"smart_camera_count": len(smart_cameras), "wanted_count": len(wanteds)}


@router.post("/list", response_model=TenantEntityCreateListResponse)
def create_tenant_entity_list(
    data: List[TenantEntityCreateExternal],
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    error_list = []
    created_list = []
    for item in data:
        try:
            district = db.query(District).filter_by(external_id=item.district_code, is_active=True).first()
            if not district:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="District not found")
            parent_entity = (
                db.query(TenantEntity)
                .filter(
                    and_(
                        TenantEntity.tenant_id == tenant_admin.tenant_id,
                        TenantEntity.hierarchy_level == 2,
                        TenantEntity.is_active,
                        TenantEntity.region_id == district.region_id,
                    )
                )
                .first()
            )
            if not parent_entity:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent Entity not found")
            duplicate_entity = (
                db.query(TenantEntity)
                .filter_by(
                    tenant_id=tenant_admin.tenant_id, external_id=item.external_id, hierarchy_level=3, is_active=True
                )
                .filter(TenantEntity.external_id.is_not(None))
                .first()
            )
            if duplicate_entity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"TenantEntity already exists with external_id={item.external_id}",
                )
            new_tenant_entity = TenantEntity(
                parent_id=parent_entity.id,
                name=item.name,
                district_id=district.id,
                country_id=1,
                region_id=district.region_id,
                tenant_id=tenant_admin.tenant_id,
                hierarchy_level=3,
                external_id=item.external_id,
                lat=item.lat,
                lon=item.lon,
                mahalla_code=item.mahalla_code,
                tin=item.tin,
                phone=item.phone,
                director_name=item.director_name,
                director_pinfl=item.director_pinfl,
                director_image=item.director_image,
            )
            db.add(new_tenant_entity)
            db.commit()
            db.refresh(new_tenant_entity)
            created_list.append({"id": new_tenant_entity.id, "external_id": new_tenant_entity.external_id})
        except Exception as e:
            error_list.append({"entity": item, "error": str(e)})
    return {
        "total_count": len(data),
        "created_list": created_list,
        "error_count": len(error_list),
        "error_list": error_list,
    }


@router.post("/", response_model=TenantEntityInDB)
def create_tenant_entity(
    tenant_entity: TenantEntityCreate, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_tenant_entity.create_tenant_entity(db, tenant_admin.tenant_id, tenant_entity)


@router.get("/", response_model=CustomPage[TenantEntityInDB])
def get_tenant_entities(
    search: Optional[str] = Query(None, alias="search"),
    hierarchy_level: Optional[int] = Query(None, alias="hierarchy_level"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_tenant_entity.get_tenant_entities(db, tenant_admin.tenant_id, hierarchy_level, search)
    return paginate(query_set)


@router.get("/all", response_model=CustomPage[TenantEntityInDB])
def get_all_tenant_entities(
    search: Optional[str] = Query(None, alias="search"),
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_tenant_entity.get_tenant_entities_all(db, tenant_admin.tenant_id, is_active, search)
    return paginate(query_set)


@router.get("/for_filter/all", response_model=List[EntityForFilter])
def get_all_tenant_entities_for_filter(
    region_id: int,
    district_id: Optional[int] = Query(None, alias="district_id"),
    search: Optional[str] = Query(None, alias="search"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_tenant_entity.get_all_entities_for_filter(db, tenant_admin.tenant_id, region_id, district_id, search)


@router.get("/{pk}", response_model=TenantEntityInDB)
def get_tenant_entity(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_tenant_entity.get_tenant_entity(db, tenant_admin.tenant_id, pk, is_active)


@router.put("/{pk}", response_model=TenantEntityInDB)
def update_tenant_entity(
    pk: int,
    tenant_entity: TenantEntityUpdate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_tenant_entity.update_tenant_entity(db, tenant_admin.tenant_id, pk, tenant_entity)


@router.delete("/{pk}", response_model=TenantEntityInDB)
def delete_tenant_entity(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    return db_tenant_entity.delete_tenant_entity(db, tenant_admin.tenant_id, pk)


@router.get("/{tenant_entity_id}/children", response_model=CustomPage[TenantEntityInDB])
def get_tenant_entity_children(
    tenant_entity_id: int,
    search: Optional[str] = Query(None, alias="search"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_tenant_entity.get_tenant_entity_children(db, tenant_admin.tenant_id, tenant_entity_id, search)
    return paginate(query_set)


@router.get("/filtered/detailed", response_model=Page[TenantEntityFilteredDetails])
def get_tenant_entity_details(
    region_id: int,
    district_id: int,
    search: Optional[str] = None,
    db: Session = Depends(get_pg_db),
    params: Params = Depends(),
    tenant_admin=Security(get_current_tenant_admin),
):
    return iterable_paginate(
        db_tenant_entity.get_tenant_entities_filterd_detailed(
            db, tenant_id=tenant_admin.tenant_id, region_id=region_id, district_id=district_id, search=search
        ),
        params=params,
    )


def get_tenant_entity_by_smart_camera(db: Session, smart_camera_id: int):
    return (
        db.query(TenantEntity)
        .join(SmartCamera, SmartCamera.tenant_entity_id == TenantEntity.id)
        .filter(SmartCamera.id == smart_camera_id)
        .first()
    )


@router.websocket("/attendance/live")
async def get_live_attendaces(
    websocket: WebSocket,
    country_id: Optional[int] = None,
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    rabbitmq: AbstractRobustConnection = Depends(get_rabbitmq_connection),
):
    await websocket.accept()
    channel = await rabbitmq.channel()

    try:
        exchange = await channel.get_exchange("amq.fanout", ensure=True)

        queue = await channel.declare_queue(exclusive=True)

        await queue.bind(exchange)

        async for message in queue:
            async with message.process():
                attendance = json.loads(message.body.decode())

                if attendance.get("attendance_id") and attendance.get("attendance_category"):
                    current_tenant_entity = db.query(TenantEntity).filter_by(id=attendance.get("tenant_entity_id"))

                    if country_id:
                        current_tenant_entity = current_tenant_entity.filter_by(country_id=country_id)

                    if region_id:
                        current_tenant_entity = current_tenant_entity.filter_by(region_id=region_id)

                    if district_id:
                        current_tenant_entity = current_tenant_entity.filter_by(district_id=district_id)

                    current_tenant_entity = current_tenant_entity.first()

                    if attendance.get("attendance_category") == "usual":
                        current_attendance = db.query(Attendance).filter_by(id=attendance.get("attendance_id")).first()

                        with contextlib.suppress(Exception):
                            await websocket.send_json(
                                {
                                    "attendance": {
                                        "id": current_attendance.id,
                                        "smart_camera_id": current_attendance.smart_camera_id,
                                        "attendance_type": current_attendance.attendance_type,
                                        "created_at": current_attendance.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                                        "tenant_entity": {
                                            "id": current_tenant_entity.id,
                                            "name": current_tenant_entity.name,
                                            "external_id": current_tenant_entity.external_id,
                                            "lon": current_tenant_entity.lon,
                                            "lat": current_tenant_entity.lat,
                                        },
                                        "identity": {
                                            "id": current_attendance.identity.id,
                                            "first_name": current_attendance.identity.first_name,
                                            "last_name": current_attendance.identity.last_name,
                                            "pinfl": current_attendance.identity.pinfl,
                                            "photo": current_attendance.identity.photo,
                                            "identity_group": current_attendance.identity.identity_group,
                                            "is_wanted": False,
                                        },
                                    }
                                }
                            )

                    elif attendance.get("attendance_category") == "wanted":
                        current_attendance = (
                            db.query(WantedAttendance).filter_by(id=attendance.get("attendance_id")).first()
                        )

                        if current_attendance:
                            currenat_tenant_entity = get_tenant_entity_by_smart_camera(
                                db=db, smart_camera_id=current_attendance.smart_camera_id
                            )
                            current_wanted = db.query(Wanted).filter_by(id=current_attendance.wanted_id).first()

                            with contextlib.suppress(Exception):
                                await websocket.send_json(
                                    {
                                        "attendance": {
                                            "id": current_attendance.id,
                                            "smart_camera_id": current_attendance.smart_camera_id,
                                            "attendance_type": current_attendance.attendance_type,
                                            "created_at": current_attendance.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                                            "tenant_entity": {
                                                "id": currenat_tenant_entity.id if currenat_tenant_entity else None,
                                                "name": currenat_tenant_entity.name if currenat_tenant_entity else None,
                                                "external_id": currenat_tenant_entity.external_id
                                                if currenat_tenant_entity
                                                else None,
                                                "lon": currenat_tenant_entity.lon if currenat_tenant_entity else None,
                                                "lat": currenat_tenant_entity.lat if currenat_tenant_entity else None,
                                            },
                                            "identity": {
                                                "id": current_wanted.id,
                                                "first_name": current_wanted.first_name,
                                                "last_name": current_wanted.last_name,
                                                "pinfl": current_wanted.pinfl,
                                                "photo": current_wanted.photo,
                                                "identity_group": None,
                                                "is_wanted": True,
                                            },
                                        }
                                    }
                                )

                    elif attendance.get("attendance_category") == "visitor":
                        current_attendance = (
                            db.query(VisitorAttendance).filter_by(id=attendance.get("attendance_id")).first()
                        )

                        if current_attendance:
                            currenat_tenant_entity = get_tenant_entity_by_smart_camera(
                                db=db, smart_camera_id=current_attendance.smart_camera_id
                            )
                            with contextlib.suppress(Exception):
                                await websocket.send_json(
                                    {
                                        "attendance": {
                                            "id": current_attendance.id,
                                            "smart_camera_id": current_attendance.smart_camera_id,
                                            "attendance_type": current_attendance.attendance_type,
                                            "created_at": current_attendance.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                                            "tenant_entity": {
                                                "id": currenat_tenant_entity.id if currenat_tenant_entity else None,
                                                "name": currenat_tenant_entity.name if currenat_tenant_entity else None,
                                                "external_id": currenat_tenant_entity.external_id
                                                if currenat_tenant_entity
                                                else None,
                                                "lon": currenat_tenant_entity.lon if currenat_tenant_entity else None,
                                                "lat": currenat_tenant_entity.lat if currenat_tenant_entity else None,
                                            },
                                            "identity": {
                                                "id": None,
                                                "first_name": None,
                                                "last_name": None,
                                                "pinfl": None,
                                                "photo": current_attendance.snapshot_url,
                                                "identity_group": 2,
                                                "is_wanted": False,
                                            },
                                        }
                                    }
                                )

                    elif attendance.get("attendance_category") == "relative-visitor":
                        current_attendance = (
                            db.query(RelativeAttendance).filter_by(id=attendance.get("attendance_id")).first()
                        )

                        if current_attendance:
                            currenat_tenant_entity = get_tenant_entity_by_smart_camera(
                                db=db, smart_camera_id=current_attendance.smart_camera_id
                            )

                            current_relative = db.query(Relative).filter_by(id=current_attendance.relative_id).first()

                            with contextlib.suppress(Exception):
                                await websocket.send_json(
                                    {
                                        "attendance": {
                                            "id": current_attendance.id,
                                            "smart_camera_id": current_attendance.smart_camera_id,
                                            "attendance_type": current_attendance.attendance_type,
                                            "created_at": current_attendance.created_at.strftime("%Y-%m-%dT%H:%M:%S"),
                                            "tenant_entity": {
                                                "id": currenat_tenant_entity.id if currenat_tenant_entity else None,
                                                "name": currenat_tenant_entity.name if currenat_tenant_entity else None,
                                                "external_id": currenat_tenant_entity.external_id
                                                if currenat_tenant_entity
                                                else None,
                                                "lon": currenat_tenant_entity.lon if currenat_tenant_entity else None,
                                                "lat": currenat_tenant_entity.lat if currenat_tenant_entity else None,
                                            },
                                            "identity": {
                                                "id": current_relative.id if current_relative else None,
                                                "first_name": current_relative.first_name if current_relative else None,
                                                "last_name": current_relative.last_name if current_relative else None,
                                                "pinfl": current_relative.pinfl if current_relative.pinfl else None,
                                                "photo": current_attendance.snapshot_url,
                                                "identity_group": 2,
                                                "is_wanted": False,
                                            },
                                        }
                                    }
                                )

    finally:
        await websocket.close()


@router.get("/attendance/analytics", tags=["attendances"], response_model=Page[TenantEntityAttendanceAnalytics])
async def get_tenant_entity_analytics(
    region_id: int,
    attendance_date: date,
    attendance_sort_type: Literal["asceding", "descending"],
    attendance_sort_role: Literal["employee", "kid"],
    attendance_sort_quantity: Literal["count", "ratio"],
    attendance_ratio_from: Optional[int] = None,
    attendance_ratio_to: Optional[int] = None,
    district_id: Optional[int] = None,
    tenant_entity_name_search: Optional[Any] = None,
    db: Session = Depends(get_pg_db),
    mongodb: AsyncIOMotorDatabase = Depends(get_analytics_cache_db),
    params: Params = Depends(),
    tenant_admin=Security(get_current_tenant_admin),
):
    return iterable_paginate(
        db_tenant_entity.get_tenant_entity_analytics(
            db=db,
            attedance_date=attendance_date,
            attendance_sort_type=attendance_sort_type,
            attendance_sort_role=attendance_sort_role,
            attendance_sort_quantity=attendance_sort_quantity,
            attendance_ratio_from=attendance_ratio_from,
            attendance_ratio_to=attendance_ratio_to,
            district_id=district_id,
            region_id=region_id,
            entity_name_search=tenant_entity_name_search,
        ),
        params=params,
    )


@router.get("/attendance/statistics", tags=["attendances"])
def get_tenant_entity_attendace_statistics(
    region_id: int,
    attendance_date: date,
    district_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_tenant_entity.get_tenant_entity_statistics(
        db=db,
        tenant_id=tenant_admin.tenant_id,
        attedance_date=attendance_date,
        region_id=region_id,
        district_id=district_id,
    )


@router.post("/relative/list")
def create_relative_list(
    data: List[RelativeCreate],
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    new_data = []
    error_list = []
    for item in data:
        if item.phone:
            try:
                main_image = get_image_from_query(item.photo)
                main_photo_url = make_minio_url_from_image(
                    minio_client, main_image, RELATIVE_IDENTITY_BUCKET, item.pinfl, is_check_hd=False
                )
                item.photo = main_photo_url
            except Exception as e:
                item.error = str(e)
                error_list.append(item)
                item.photo = None
        new_data.append(item.model_dump())
    create_relative_identity_list_task.delay(tenant_admin.tenant_id, new_data)
    return {"received_count": len(new_data), "errors": error_list}


@router.post("/relative/", response_model=RelativeInDB)
def create_relative(
    data: RelativeCreate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    if data.photo:
        main_image = get_image_from_query(data.photo)
        main_photo_url = make_minio_url_from_image(minio_client, main_image, RELATIVE_IDENTITY_BUCKET, data.pinfl)
        data.photo = main_photo_url

    relative_data = RelativeBase(
        first_name=data.first_name,
        last_name=data.last_name,
        photo=data.photo,
        email=data.email,
        phone=data.phone,
        pinfl=data.pinfl,
    )
    new_relative = db_relative.create_relative(db, relative_data)
    if data.kid_ids:
        for kid_id in data.kid_ids:
            identity = (
                db.query(Identity)
                .filter_by(external_id=str(kid_id), tenant_id=tenant_admin.tenant_id, identity_group=0, is_active=True)
                .first()
            )
            if identity:
                new_relative_identity = IdentityRelative(identity_id=int(str(identity.id)), relative_id=new_relative.id)
                db.add(new_relative_identity)
                db.commit()
                db.refresh(new_relative_identity)
    return new_relative


@router.get("/relative/", response_model=CustomPage[RelativeInDB])
def get_relatives(
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_relative.get_relatives(db)
    return paginate(query_set)


@router.get("/relative/update_photo_with_pinfl")
def update_photos_with_pinfl(
    tenant_entity_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    tenant_entity = (
        db.query(TenantEntity).filter_by(id=tenant_entity_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    relatives = db_relative.get_entity_relatives(db, tenant_entity_id)
    for relative in relatives:
        update_relative_photo_with_pinfl_task.delay(relative.id, tenant_admin.tenant_id)
    return {"detected_count": len(relatives)}


@router.get("/relative/upload_photo_with_task")
def upload_photo_with_task(
    tenant_entity_id: int,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    tenant_entity = (
        db.query(TenantEntity).filter_by(id=tenant_entity_id, tenant_id=tenant_admin.tenant_id, is_active=True).first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    relatives = db_relative.get_uploadable_relatives(db, tenant_entity_id)
    for relative in relatives:
        upload_relative_with_task.delay(relative.id, tenant_admin.tenant_id, tenant_entity_id)
    return {"detected_count": len(relatives)}
