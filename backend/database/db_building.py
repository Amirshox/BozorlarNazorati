from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import Building, TenantEntity
from schemas.infrastructure import BuildingBase


def get_all_buildings_no_pagination(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(Building).filter_by(tenant_id=tenant_id, is_active=is_active).all()


def get_all_buildings(db: Session, tenant_id: int, search: str = None, is_active: bool = True):
    if search is None:
        return db.query(Building).filter_by(tenant_id=tenant_id, is_active=is_active)
    return db.query(Building).filter(Building.name.ilike(f"%{search}%")).filter_by(tenant_id=tenant_id,  is_active=is_active)


def get_building(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    building = db.query(Building).filter_by(id=pk, is_active=is_active).first()
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    if building.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden access to get building")
    return building


def create_building(db: Session, building_data: BuildingBase, tenant_id: int):
    exist_building = db.query(Building).filter_by(tenant_id=tenant_id, name=building_data.name).first()
    if exist_building:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Building already exists")

    if not db.query(
        exists().where(and_(building_data.tenant_entity_id == TenantEntity.id, TenantEntity.is_active))
    ).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")

    building = Building(
        name=building_data.name,
        latitude=building_data.latitude,
        longitude=building_data.longitude,
        tenant_entity_id=building_data.tenant_entity_id,
        tenant_id=tenant_id,
    )
    db.add(building)
    db.commit()
    db.refresh(building)
    return building


def update_building(db: Session, pk: int, building_data: BuildingBase, tenant_id: int):
    exist_building = db.query(Building).filter_by(tenant_id=tenant_id, name=building_data.name).first()
    if exist_building and exist_building.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Building name({building_data.name}) already exists"
        )
    building = db.query(Building).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    if not db.query(
        exists().where(and_(building_data.tenant_entity_id == TenantEntity.id, TenantEntity.is_active))
    ).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    if building_data.name:
        building.name = building_data.name
    if building_data.latitude:
        building.latitude = building_data.latitude
    if building_data.longitude:
        building.longitude = building_data.longitude
    if building_data.tenant_entity_id:
        building.tenant_entity_id = building_data.tenant_entity_id
    db.commit()
    db.refresh(building)
    return building


def delete_building(db: Session, pk: int, tenant_id: int):
    building = db.query(Building).filter_by(id=pk, is_active=True).first()
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    if building.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden access to delete building")
    building.is_active = False
    db.commit()
    return building


def get_buildings_by_user_permissions(db: Session, user, is_active: bool = True):
    tenant_entity = db.query(TenantEntity).filter_by(id=user.tenant_entity_id).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    buildings = (
        db.query(Building)
        .filter_by(tenant_id=tenant_entity.tenant_id, is_active=is_active)
        .filter(Building.tenant_entity.has(tenant_entity.hierarchy_level >= tenant_entity.hierarchy_level))
    )
    return buildings
