from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import Building, Room, TenantEntity
from schemas.infrastructure import RoomBase


def get_all_rooms_no_pagination(db: Session, building_id: int, tenant_id: int, is_active: bool = True):
    return db.query(Room).filter_by(tenant_id=tenant_id, building_id=building_id, is_active=is_active).all()


def get_rooms(db: Session, building_id: int, tenant_id: int, is_active: bool = True):
    return db.query(Room).filter_by(tenant_id=tenant_id, building_id=building_id, is_active=is_active)


def get_room(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    room = db.query(Room).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room with id {pk} not found")
    return room


def create_room(db: Session, room_data: RoomBase, tenant_id: int):
    exist_room = (
        db.query(Room).filter_by(tenant_id=tenant_id, building_id=room_data.building_id, name=room_data.name).first()
    )
    if exist_room:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Room with name {room_data.name} already exists"
        )
    building = db.query(Building).filter_by(id=room_data.building_id, is_active=True).first()
    if not building:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")

    room = Room(
        name=room_data.name,
        description=room_data.description,
        building_id=room_data.building_id,
        floor=room_data.floor,
        tenant_id=tenant_id,
        tenant_entity_id=int(str(building.tenant_entity_id)),
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def update_room(db: Session, pk: int, room_data: RoomBase, tenant_id: int):
    same_room = (
        db.query(Room).filter_by(tenant_id=tenant_id, building_id=room_data.building_id, name=room_data.name).first()
    )
    if same_room and same_room.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Room with name {room_data.name} already exists"
        )
    room = db.query(Room).filter_by(id=pk, is_active=True).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room with id {pk} not found")
    if room_data.name:
        room.name = room_data.name
    if room_data.floor:
        room.floor = room_data.floor
    if room_data.description:
        room.description = room_data.description
    db.commit()
    db.refresh(room)
    return room


def delete_room(db: Session, pk: int):
    room = db.query(Room).filter_by(id=pk, is_active=True).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room with id {pk} not found")
    room.is_active = False
    db.commit()
    return room


def get_rooms_by_user_permissions(db: Session, user, is_active: bool = True, building_id: int = None):
    tenant_entity = db.query(TenantEntity).filter_by(id=user.tenant_entity_id).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    return db.query(Room).filter_by(tenant_id=tenant_entity.tenant_id, building_id=building_id, is_active=is_active)

def get_rooms_by_filter(db: Session, tenant_id: int, building_id: int = None, tenant_entity_id: int = None, is_active: bool = True):
    query = db.query(Room).filter_by(tenant_id=tenant_id, is_active=is_active)
    
    if building_id:
        return query.filter_by(building_id=building_id)

    if tenant_entity_id:
        return query.filter_by(tenant_entity_id=tenant_entity_id)

    return query
    