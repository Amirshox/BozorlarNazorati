from datetime import date
from itertools import groupby
from operator import itemgetter
from typing import Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, case, distinct, func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.orm.session import Session

from config import MOBILE_ALLOWED_RADIUS, MOBILE_FACE_AUTH_THRESHOLD, MOBILE_IS_LIGHT, MOBILE_SIGNATURE_KEY
from models import (
    Attendance,
    Building,
    Country,
    District,
    Identity,
    Region,
    Room,
    SmartCamera,
    Tenant,
    TenantEntity,
    VisitorAttendance,
    WantedAttendance,
)
from schemas.tenant_hierarchy_entity import TenantEntityCreate, TenantEntityUpdate


def create_tenant_entity(db: Session, tenant_id, tenant_entity: TenantEntityCreate):
    tenant = db.query(Tenant).filter_by(id=tenant_id, is_active=True).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    district = db.query(District).filter_by(id=tenant_entity.district_id, is_active=True).first()
    if tenant_entity.district_id and not district:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    parent_id = None
    if tenant_entity.hierarchy_level and tenant_entity.hierarchy_level > 1:
        if not tenant_entity.parent_id or tenant_entity.parent_id < 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid Parent Tenant entity id")
        parent_entity = db.query(TenantEntity).filter_by(tenant_id=tenant_id, id=tenant_entity.parent_id).first()
        if not parent_entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent Tenant entity not found")
        parent_id = tenant_entity.parent_id
    new_tenant_entity = TenantEntity(
        parent_id=parent_id,
        name=tenant_entity.name,
        photo=tenant_entity.photo,
        description=tenant_entity.description,
        district_id=tenant_entity.district_id,
        country_id=tenant_entity.country_id,
        region_id=tenant_entity.region_id,
        tenant_id=tenant_id,
        hierarchy_level=tenant_entity.hierarchy_level,
        trackable=tenant_entity.trackable,
        blacklist_monitoring=tenant_entity.blacklist_monitoring,
        external_id=tenant_entity.external_id,
        lat=tenant_entity.lat,
        lon=tenant_entity.lon,
        mahalla_code=tenant_entity.mahalla_code,
        tin=tenant_entity.tin,
        phone=tenant_entity.phone,
        director_name=tenant_entity.director_name,
        director_pinfl=tenant_entity.director_pinfl,
        director_image=tenant_entity.director_image,
        allowed_radius=tenant_entity.allowed_radius,
        face_auth_threshold=tenant_entity.face_auth_threshold,
        signature_key=tenant_entity.signature_key,
    )
    db.add(new_tenant_entity)
    db.commit()
    db.refresh(new_tenant_entity)
    return new_tenant_entity


def get_tenant_entity(db: Session, tenant_id, pk: int, is_active: bool = True):
    tenant_entity = db.query(TenantEntity).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    return tenant_entity


def get_tenant_entities(db: Session, tenant_id, hierarchy_level: int = 1, search: str | None = None):
    query = db.query(TenantEntity).filter_by(tenant_id=tenant_id, is_active=True, hierarchy_level=hierarchy_level)
    if search:
        query = query.filter(TenantEntity.name.ilike(f"%{search}%"))
    return query


def get_tenant_entities_all(db: Session, tenant_id, is_active: bool = True, search: str | None = None):
    query = db.query(TenantEntity).filter_by(tenant_id=tenant_id, is_active=is_active)
    if search:
        query = query.filter(TenantEntity.name.ilike(f"%{search}%"))
    return query


def get_all_entities_for_filter(
    db: Session,
    tenant_id: int,
    region_id: int,
    district_id: int | None = None,
    search: Optional[str] = None,
):
    query = (
        db.query(TenantEntity)
        .options(joinedload(TenantEntity.region))
        .options(joinedload(TenantEntity.district))
        .options(selectinload(TenantEntity.smart_cameras))
        .filter_by(tenant_id=tenant_id, region_id=region_id, is_active=True)
    )
    if district_id:
        query = query.filter(TenantEntity.district_id == district_id)
    if search:
        query = query.filter(TenantEntity.name.ilike(f"%{search}%"))
    return query.all()


def update_tenant_entity(db: Session, tenant_id: int, pk: int, tenant_entity: TenantEntityUpdate):
    parent_id = None
    if tenant_entity.hierarchy_level and tenant_entity.hierarchy_level > 1:
        if not tenant_entity.parent_id or tenant_entity.parent_id < 1:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid Parent Tenant entity id")
        parent_entity = db.query(TenantEntity).filter_by(tenant_id=tenant_id, id=tenant_entity.parent_id).first()
        if not parent_entity:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent Tenant entity not found")
        parent_id = tenant_entity.parent_id
    tenant_entity_db = db.query(TenantEntity).filter_by(id=pk, tenant_id=tenant_id).first()
    if not tenant_entity_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    if tenant_entity.name:
        tenant_entity_db.name = tenant_entity.name
    if tenant_entity.photo:
        tenant_entity_db.photo = tenant_entity.photo
    if tenant_entity.description:
        tenant_entity_db.description = tenant_entity.description
    if tenant_entity.district_id:
        tenant_entity_db.district_id = tenant_entity.district_id
    if tenant_entity.country_id:
        tenant_entity_db.country_id = tenant_entity.country_id
    if tenant_entity.region_id:
        tenant_entity_db.region_id = tenant_entity.region_id
    if tenant_entity.hierarchy_level:
        tenant_entity_db.hierarchy_level = tenant_entity.hierarchy_level
    if tenant_entity.parent_id:
        tenant_entity_db.parent_id = parent_id
    if tenant_entity.trackable is not None:
        tenant_entity_db.trackable = tenant_entity.trackable
    if tenant_entity.blacklist_monitoring is not None:
        tenant_entity_db.blacklist_monitoring = tenant_entity.blacklist_monitoring
    if tenant_entity.external_id:
        tenant_entity_db.external_id = tenant_entity.external_id
    if tenant_entity.lat:
        tenant_entity_db.lat = tenant_entity.lat
    if tenant_entity.lon:
        tenant_entity_db.lon = tenant_entity.lon
    if tenant_entity.mahalla_code:
        tenant_entity_db.mahalla_code = tenant_entity.mahalla_code
    if tenant_entity.tin:
        tenant_entity_db.tin = tenant_entity.tin
    if tenant_entity.phone:
        tenant_entity_db.phone = tenant_entity.phone
    if tenant_entity.director_name:
        tenant_entity_db.director_name = tenant_entity.director_name
    if tenant_entity.director_pinfl:
        tenant_entity_db.director_pinfl = tenant_entity.director_pinfl
    if tenant_entity.director_image:
        tenant_entity_db.director_image = tenant_entity.director_image
    if tenant_entity.allowed_radius:
        tenant_entity_db.allowed_radius = tenant_entity.allowed_radius
    if tenant_entity.face_auth_threshold:
        tenant_entity_db.face_auth_threshold = tenant_entity.face_auth_threshold
    if tenant_entity.signature_key:
        tenant_entity_db.signature_key = tenant_entity.signature_key
    db.commit()
    db.refresh(tenant_entity_db)
    return tenant_entity_db


def delete_tenant_entity(db: Session, tenant_id: int, pk: int):
    tenant_entity = db.query(TenantEntity).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    tenant_entity.is_active = False
    db.commit()
    return tenant_entity


def get_tenant_entity_children(db: Session, tenant_id: int, tenant_entity_id: int, search: str | None = None):
    query = db.query(TenantEntity).filter_by(tenant_id=tenant_id, parent_id=tenant_entity_id, is_active=True)
    if search:
        query = query.filter(TenantEntity.name.ilike(f"%{search}%"))
    return query


def get_tenant_entities_by_filter(
    db: Session,
    tenant_id: int,
    tenant_entity_id: int = None,
    region_id: int = None,
    district_id: int = None,
):
    query = db.query(TenantEntity).filter_by(tenant_id=tenant_id, is_active=True)
    if tenant_entity_id:
        query = query.filter_by(id=tenant_entity_id)
    if region_id:
        query = query.filter_by(region_id=region_id)
    if district_id:
        query = query.filter_by(district_id=district_id)
    return query


def get_tenant_entities_filterd_detailed(
    db: Session, tenant_id: int, search: str = None, region_id: int = None, district_id: int = None
):
    query = db.query(
        TenantEntity.id,
        TenantEntity.name,
        TenantEntity.external_id,
        TenantEntity.allowed_radius,
        TenantEntity.face_auth_threshold,
        TenantEntity.spoofing_threshold,
        TenantEntity.signature_key,
        TenantEntity.ignore_location_restriction,
        TenantEntity.lon,
        TenantEntity.lat,
    ).filter(and_(TenantEntity.tenant_id == tenant_id, TenantEntity.is_active))

    if search:
        query = query.filter(TenantEntity.name.ilike(f"%{search}%"))

    if region_id:
        query = query.filter(TenantEntity.region_id == region_id)

    if district_id:
        query = query.filter(TenantEntity.district_id == district_id)

    tenant_entities = []

    for each_tenant_entity in query:
        smart_camera_count = len(
            db.query(SmartCamera)
            .filter(SmartCamera.tenant_entity_id == each_tenant_entity.id, SmartCamera.is_active)
            .all()
        )

        room_count = len(db.query(Room).filter(Room.tenant_entity_id == each_tenant_entity.id, Room.is_active).all())

        building_count = len(
            db.query(Building).filter(Building.tenant_entity_id == each_tenant_entity.id, Building.is_active).all()
        )

        tenant_entities.append(
            {
                "id": each_tenant_entity.id,
                "name": each_tenant_entity.name,
                "external_id": each_tenant_entity.external_id,
                "allowed_radius": each_tenant_entity.allowed_radius,
                "face_auth_threshold": each_tenant_entity.face_auth_threshold,
                "spoofing_threshold": each_tenant_entity.spoofing_threshold,
                "signature_key": each_tenant_entity.signature_key,
                "ignore_location_restriction": each_tenant_entity.ignore_location_restriction,
                "lon": each_tenant_entity.lon,
                "lat": each_tenant_entity.lat,
                "smart_camera_count": smart_camera_count,
                "room_count": room_count,
                "building_count": building_count,
            }
        )

    return tenant_entities


def get_tenant_entities_by_district_id(db: Session, district_id: int):
    return db.query(TenantEntity).filter_by(district_id=district_id, hierarchy_level=3, is_active=True).all()


def get_tenant_entities_by_region_id(db: Session, region_id: int):
    return (
        db.query(TenantEntity)
        .join(District, TenantEntity.district_id == District.id)
        .join(Region, District.region_id == Region.id)
        .filter(and_(Region.id == region_id, TenantEntity.hierarchy_level == 3))
        .options(joinedload(TenantEntity.smart_cameras))
        .all()
    )


def get_tenant_entities_by_country_id(db: Session, country_id: int):
    return (
        db.query(TenantEntity)
        .join(District, TenantEntity.district_id == District.id)
        .join(Region, District.region_id == Region.id)
        .join(Country, Region.country_id == Country.id)
        .filter(and_(Country.id == country_id, TenantEntity.hierarchy_level == 3))
        .options(joinedload(TenantEntity.smart_cameras))
        .all()
    )


def haversine(lat1, lon1, lat2, lon2):
    # Calculate the great-circle distance between two points
    # on the Earth using the Haversine formula
    return 6371 * func.acos(
        func.cos(func.radians(lat1)) * func.cos(func.radians(lat2)) * func.cos(func.radians(lon2) - func.radians(lon1))
        + func.sin(func.radians(lat1)) * func.sin(func.radians(lat2))
    )


def get_tenant_entities_by_location(db: Session, latitude: float, longitude: float, radius_km: float):
    subquery = (
        db.query(Building.tenant_entity_id)
        .filter(haversine(latitude, longitude, Building.latitude, Building.longitude) <= radius_km)
        .subquery()
    )

    return (
        db.query(TenantEntity)
        .filter(and_(TenantEntity.id.in_(subquery), TenantEntity.hierarchy_level == 3))
        .options(joinedload(TenantEntity.smart_cameras))
        .all()
    )


def get_tenant_entity_info(db: Session, tenant_id: int, tenant_entity_id: int):
    instance = db.query(TenantEntity).filter_by(tenant_id=tenant_id, id=tenant_entity_id, is_active=True).first()
    if not instance:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    instance.allowed_radius = instance.allowed_radius or MOBILE_ALLOWED_RADIUS
    instance.face_auth_threshold = instance.face_auth_threshold or MOBILE_FACE_AUTH_THRESHOLD
    instance.signature_key = instance.signature_key or MOBILE_SIGNATURE_KEY
    instance.is_light = instance.is_light or MOBILE_IS_LIGHT
    return instance


def get_tenant_entity_statistics(
    db: Session,
    tenant_id: int,
    attedance_date: date,
    region_id: int = None,
    district_id: int = None,
):
    filtered_tenant_entities = db.query(TenantEntity.id).filter(
        TenantEntity.is_active, TenantEntity.tenant_id == tenant_id
    )

    if region_id:
        filtered_tenant_entities = filtered_tenant_entities.filter_by(region_id=region_id)

    if district_id:
        filtered_tenant_entities = filtered_tenant_entities.filter_by(district_id=district_id)

    filtered_tenant_entities = filtered_tenant_entities.subquery()

    attendance_statistics = (
        db.query(
            Identity.identity_group.label("identity_group"),
            func.count(distinct(Attendance.identity_id)).label("identity_count"),
        )
        .join(Identity, Attendance.identity_id == Identity.id)
        .filter(
            Attendance.tenant_entity_id.in_(filtered_tenant_entities),
            Attendance.attendance_datetime.between(f"{attedance_date} 00:00:00", f"{attedance_date} 23:59:59"),
        )
        .group_by(
            Identity.identity_group,
        )
        .all()
    )

    visitor_attendance_statistics = (
        db.query(VisitorAttendance)
        .join(SmartCamera, VisitorAttendance.smart_camera_id == SmartCamera.id)
        .filter(
            VisitorAttendance.attendance_datetime.between(f"{attedance_date} 00:00:00", f"{attedance_date} 23:59:59"),
            SmartCamera.tenant_entity_id.in_(filtered_tenant_entities),
        )
        .all()
    )

    wanted_attendance_statistics = (
        db.query(WantedAttendance)
        .filter(
            WantedAttendance.attendance_datetime.between(f"{attedance_date} 00:00:00", f"{attedance_date} 23:59:59"),
            WantedAttendance.tenant_id == tenant_id,
        )
        .all()
    )

    statistics_report = {}

    students_and_teachers = 0

    for each_record in attendance_statistics:
        if each_record.identity_group == 0 or each_record.identity_group == 1:
            students_and_teachers += each_record.identity_count

    statistics_report["students_teachers"] = students_and_teachers
    statistics_report["wanted"] = len(wanted_attendance_statistics)
    statistics_report["visitors"] = len(visitor_attendance_statistics)

    return statistics_report


def get_tenant_entity_analytics(
    db: Session,
    attedance_date: date,
    attendance_sort_type: Literal["ascending", "descending"],
    attendance_sort_role: Literal["employee", "kid"],
    attendance_sort_quantity: Literal["count", "ratio"],
    region_id: int = None,
    district_id: int = None,
    entity_name_search: str = None,
    attendance_ratio_from: int = None,
    attendance_ratio_to: int = None,
):
    filtered_tenant_entities = db.query(TenantEntity.id).filter(TenantEntity.is_active)

    if region_id:
        filtered_tenant_entities = filtered_tenant_entities.filter_by(region_id=region_id)

    if district_id:
        filtered_tenant_entities = filtered_tenant_entities.filter_by(district_id=district_id)

    if entity_name_search:
        filtered_tenant_entities = filtered_tenant_entities.filter(TenantEntity.name.ilike(f"%{entity_name_search}%"))

    filtered_tenant_entities = filtered_tenant_entities.subquery()

    attendance_analytics = (
        db.query(
            Attendance.tenant_entity_id,
            TenantEntity.name.label("entity_name"),
            TenantEntity.external_id.label("entity_external_id"),
            Identity.identity_group.label("identity_group"),
            func.count(distinct(Attendance.identity_id)).label("identity_count"),
        )
        .join(TenantEntity, Attendance.tenant_entity_id == TenantEntity.id)
        .join(Identity, Attendance.identity_id == Identity.id)
        .filter(
            Attendance.tenant_entity_id.in_(filtered_tenant_entities),
            Attendance.attendance_datetime.between(f"{attedance_date} 00:00:00", f"{attedance_date} 23:59:59"),
        )
        .group_by(
            Attendance.tenant_entity_id,
            TenantEntity.name,
            TenantEntity.external_id,
            Identity.identity_group,
        )
        .all()
    )

    TENANT_ENTITY_ID_INDEX = 0
    IDENTITY_GROUP_INDEX = 3
    IDENTITY_COUNT_INDEX = 4

    attendance_analytics.sort(key=itemgetter(TENANT_ENTITY_ID_INDEX))
    attendance_analytics = {
        key: list(group) for key, group in groupby(attendance_analytics, key=itemgetter(TENANT_ENTITY_ID_INDEX))
    }

    analytics_reports = []

    for tenant_entity_id, group in attendance_analytics.items():
        total_count = (
            db.query(
                func.count(case((Identity.identity_group == 0, 1))).label("total_kids_count"),
                func.count(case((Identity.identity_group == 1, 1))).label("total_employees_count"),
            )
            .filter(Identity.tenant_entity_id == tenant_entity_id)
            .one()
        )

        kids_attendance_count = 0
        employees_attendance_count = 0

        for row in group:
            if row[IDENTITY_GROUP_INDEX] == 0:
                kids_attendance_count = row[IDENTITY_COUNT_INDEX]
            elif row[IDENTITY_GROUP_INDEX] == 1:
                employees_attendance_count = row[IDENTITY_COUNT_INDEX]

        if total_count.total_kids_count == 0 or total_count.total_employees_count == 0:
            continue

        kids_attendance_ratio = round((kids_attendance_count / total_count.total_kids_count) * 100, 2)
        employees_attendance_ratio = round((employees_attendance_count / total_count.total_employees_count) * 100, 2)

        current_analytics_data = group[0]

        if (attendance_ratio_from is not None) and (attendance_ratio_to is not None):
            if attendance_sort_role == "kid":
                if attendance_ratio_from <= kids_attendance_ratio <= attendance_ratio_to:
                    analytics_reports.append(
                        {
                            "tenant_entity_id": current_analytics_data.tenant_entity_id,
                            "tenant_entity_name": current_analytics_data.entity_name,
                            "external_id": current_analytics_data.entity_external_id,
                            "kids_attendance_count": kids_attendance_count,
                            "employees_attendance_count": employees_attendance_count,
                            "kids_total_count": total_count.total_kids_count,
                            "employees_total_count": total_count.total_employees_count,
                            "attendance_ratio": kids_attendance_ratio,
                        }
                    )

            elif attendance_sort_role == "employee":  # noqa
                if attendance_ratio_from <= employees_attendance_ratio <= attendance_ratio_to:
                    analytics_reports.append(
                        {
                            "tenant_entity_id": current_analytics_data.tenant_entity_id,
                            "tenant_entity_name": current_analytics_data.entity_name,
                            "external_id": current_analytics_data.entity_external_id,
                            "kids_attendance_count": kids_attendance_count,
                            "employees_attendance_count": employees_attendance_count,
                            "kids_total_count": total_count.total_kids_count,
                            "employees_total_count": total_count.total_employees_count,
                            "attendance_ratio": employees_attendance_ratio,
                        }
                    )
        else:
            analytics_reports.append(
                {
                    "tenant_entity_id": current_analytics_data.tenant_entity_id,
                    "tenant_entity_name": current_analytics_data.entity_name,
                    "external_id": current_analytics_data.entity_external_id,
                    "kids_attendance_count": kids_attendance_count,
                    "employees_attendance_count": employees_attendance_count,
                    "kids_total_count": total_count.total_kids_count,
                    "employees_total_count": total_count.total_employees_count,
                    "attendance_ratio": kids_attendance_ratio
                    if attendance_sort_role == "kid"
                    else employees_attendance_ratio,
                }
            )

    if attendance_sort_quantity == "ratio":
        return sorted(
            analytics_reports,
            key=lambda eachReport: eachReport["attendance_ratio"],
            reverse=(attendance_sort_type == "descending"),
        )
    elif attendance_sort_quantity == "count":
        if attendance_sort_role == "kid":
            return sorted(
                analytics_reports,
                key=lambda eachReport: eachReport["kids_attendance_count"],
                reverse=(attendance_sort_type == "descending"),
            )
        elif attendance_sort_role == "employee":
            return sorted(
                analytics_reports,
                key=lambda eachReport: eachReport["employees_attendance_count"],
                reverse=(attendance_sort_type == "descending"),
            )

    return analytics_reports
