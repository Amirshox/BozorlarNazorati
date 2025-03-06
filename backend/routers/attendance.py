from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin, get_tenant_entity_user
from database import db_attendance, db_smartcamera, db_tenant_entity
from database.database import get_pg_db
from schemas.attendance import AttendanceInDB, WantedAttendanceInDB
from schemas.visitor import VisitorAttendanceInDB
from utils.pagination import CustomPage

router = APIRouter(prefix="/attendance", tags=["attendance"])

customer_router = APIRouter(prefix="/attendances", tags=["attendances"])
tenant_router = APIRouter(prefix="/attendances", tags=["attendances"])


@router.get("/visitor", response_model=CustomPage[VisitorAttendanceInDB])
def smart_camera_visitor_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    query_set = db_smartcamera.get_user_attendances(db, "visitor", smart_camera_id, limit)
    return paginate(query_set)


@router.get("/identity", response_model=CustomPage[AttendanceInDB])
def smart_camera_identity_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    query_set = db_smartcamera.get_user_attendances(db, "identity", smart_camera_id, limit)
    return paginate(query_set)


@router.get("/wanted", response_model=CustomPage[WantedAttendanceInDB])
def smart_camera_wanted_attendances(
    smart_camera_id: int,
    limit: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    query_set = db_smartcamera.get_user_attendances(db, "wanted", smart_camera_id, limit)
    return paginate(query_set)


@customer_router.get("", response_model=CustomPage[AttendanceInDB])
def get_customer_attendances(
    identity_group: Optional[int] = None,
    event_type: Optional[str] = None,
    start_date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    end_date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    from_comp_score: Optional[float] = None,
    to_comp_score: Optional[float] = None,
    by_mobile: Optional[bool] = None,
    search: Optional[str] = None,
    unique: Optional[bool] = False,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
):
    try:
        query_set = db_attendance.get_attendance_with_filters(
            db=db,
            tenant_id=user.tenant_id,
            tenant_entity_id=user.tenant_entity_id,
            identity_group=identity_group,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            from_comp_score=from_comp_score,
            to_comp_score=to_comp_score,
            by_mobile=by_mobile,
            search=search,
            unique=unique,
        )
        return paginate(query_set)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Ouch! Something went wrong") from e


@tenant_router.get("", response_model=CustomPage[AttendanceInDB])
def get_attendances(
    tenant_entity_id: Optional[int] = None,
    identity_group: Optional[int] = None,
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
    event_type: Optional[str] = None,
    start_date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    end_date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    from_comp_score: Optional[float] = None,
    to_comp_score: Optional[float] = None,
    by_mobile: Optional[bool] = None,
    search: Optional[str] = None,
    unique: Optional[bool] = False,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    if tenant_entity_id:
        entity = db_tenant_entity.get_tenant_entity(db, tenant_admin.tenant_id, tenant_entity_id)  # noqa
    tenant_entities = db_tenant_entity.get_tenant_entities_by_filter(
        db=db,
        tenant_id=tenant_admin.tenant_id,
        tenant_entity_id=tenant_entity_id,
        region_id=region_id,
        district_id=district_id,
    )

    if tenant_entities.count() == 0:
        raise HTTPException(status_code=400, detail="Ouch! No tenant entities found")

    try:
        query_set = db_attendance.get_attendance_with_filters(
            db=db,
            tenant_id=tenant_admin.tenant_id,
            tenant_entity_id=tenant_entity_id,
            identity_group=identity_group,
            region_id=region_id,
            district_id=district_id,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
            from_comp_score=from_comp_score,
            to_comp_score=to_comp_score,
            by_mobile=by_mobile,
            search=search,
            unique=unique,
        )
        return paginate(query_set)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="Ouch! Something went wrong") from e
