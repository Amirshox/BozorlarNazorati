from datetime import datetime, timedelta
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.session import Session

from models import Attendance, Identity, TenantEntity


def get_attendances(db: Session, identity_id: int):
    return (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .filter_by(identity_id=identity_id, is_active=True)
    )


def get_attendance_with_filters(
    db: Session,
    tenant_id: int,
    region_id: int = None,
    district_id: int = None,
    tenant_entity_id: int = None,
    identity_group: int = None,
    event_type: str = None,
    start_date: datetime = None,
    end_date: datetime = None,
    from_comp_score: float = None,
    to_comp_score: float = None,
    by_mobile: bool = None,
    search: str = None,
    unique: bool = False,
):
    query = (
        db.query(Attendance)
        .options(joinedload(Attendance.identity))
        .options(selectinload(Attendance.spoofing))
        .options(joinedload(Attendance.package))
        .join(Identity, Attendance.identity_id == Identity.id)
        .join(TenantEntity, TenantEntity.id == Attendance.tenant_entity_id)
        .filter(Attendance.is_active, Attendance.tenant_id == tenant_id)
    )
    if tenant_entity_id:
        query = query.filter(TenantEntity.id == tenant_entity_id)
    if identity_group is not None:
        query = query.filter(Identity.identity_group == identity_group)
    if region_id:
        query = query.filter(TenantEntity.region_id == region_id)
    if district_id:
        query = query.filter(TenantEntity.district_id == district_id)
    if event_type:
        query = query.filter(Attendance.attendance_type == event_type)
    if start_date:
        query = query.filter(Attendance.attendance_datetime >= start_date)
    if end_date:
        query = query.filter(Attendance.attendance_datetime < end_date)
    if from_comp_score is not None:
        query = query.filter(Attendance.comp_score >= from_comp_score)
    if to_comp_score is not None:
        query = query.filter(Attendance.comp_score < to_comp_score)
    if by_mobile is not None:
        query = query.filter(Attendance.by_mobile == by_mobile)
    if search:
        query = query.filter(
            Identity.first_name.ilike(f"%{search}%")
            | Identity.last_name.ilike(f"%{search}%")
            | Identity.pinfl.ilike(f"%{search}%")
        )
    if unique is True:
        query = query.distinct(Attendance.identity_id).order_by(Attendance.identity_id.desc())
    return query.order_by(Attendance.id.desc())


def get_yesterday_attendances_by_entity_id(db: Session, tenant_id: int, tenant_entity_id: int):
    entity = db.query(TenantEntity).filter_by(tenant_id=tenant_id, id=tenant_entity_id, is_active=True).first()
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Entity not found")

    yesterday = datetime.utcnow() - timedelta(days=1)
    yesterday_start = datetime.combine(yesterday.date(), datetime.min.time())
    yesterday_end = datetime.combine(yesterday.date(), datetime.max.time())

    return (
        db.query(Attendance)
        .filter(
            and_(
                Attendance.tenant_entity_id == tenant_entity_id,
                Attendance.attendance_datetime >= yesterday_start,
                Attendance.attendance_datetime <= yesterday_end,
            )
        )
        .all()
    )


def get_attendance_stats(db: Session, tenant_id: int, tenant_entity_id: int, date: datetime) -> Tuple[int, int, int]:
    start_datetime = datetime.combine(date.date(), datetime.min.time())
    end_datetime = datetime.combine(date.date(), datetime.max.time())
    total_kids = (
        db.query(Identity)
        .filter_by(tenant_entity_id=tenant_entity_id, identity_group=0, identity_type="kid", is_active=True)
        .all()
    )
    total_ids = [_.id for _ in total_kids]
    attending_kids = (
        db.query(Attendance.id)
        .filter(
            and_(
                Attendance.identity_id.in_(total_ids),
                Attendance.attendance_datetime >= start_datetime,
                Attendance.attendance_datetime <= end_datetime,
                Attendance.is_active,
                Attendance.tenant_id == tenant_id,
            )
        )
        .distinct(Attendance.identity_id)
        .count()
    )
    absent_kids = len(total_kids) - attending_kids
    return len(total_kids), attending_kids, absent_kids
