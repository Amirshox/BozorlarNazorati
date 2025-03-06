from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session
from typing import Literal

from models import Building, Camera, CameraSnapshot, Room, Tenant, TenantEntity
from schemas.infrastructure import CameraBase, CameraCreate


def get_cameras(db: Session, room_id: int, tenant_id: int, is_active: bool = True):
    return db.query(Camera).filter_by(tenant_id=tenant_id, room_id=room_id, is_active=is_active)

def get_cameras_by_option(db: Session, id: int, selection_type: Literal['building', 'room'], is_active: bool = True):
    if selection_type == 'room':
        return db.query(Camera).filter_by(room_id=id, is_active=is_active)
    elif selection_type == 'building':
        building_rooms = db.query(Room).filter_by(building_id=id).all()

        building_room_ids = []

        for each_room in building_rooms:
            building_room_ids.append(each_room.id)

        return db.query(Camera).filter(and_(Camera.room_id.in_(building_room_ids), Camera.is_active == is_active))


def get_camera(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    camera = db.query(Camera).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera with id {pk} not found")
    return camera


def get_camera_snapshots(db: Session, camera_id: int, tenant_id: int):
    camera = db.query(Camera).filter_by(tenant_id=tenant_id, id=camera_id, is_active=True).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You have no access to this Camera")
    return db.query(CameraSnapshot).filter_by(camera_id=camera_id, is_active=True)


def create_camera(db: Session, camera_data: CameraCreate, tenant_id: int):
    exist_camera = (
        db.query(Camera).filter_by(tenant_id=tenant_id, room_id=camera_data.room_id, name=camera_data.name).first()
    )
    if exist_camera:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Camera with name {camera_data.name} already exists"
        )
    if not db.query(exists().where(and_(Tenant.id == tenant_id, Tenant.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant not found")
    building = (
        db.query(Building)
        .join(Room, Room.building_id == Building.id)
        .filter(and_(Room.id == camera_data.room_id, Room.is_active))
        .first()
    )
    if not building:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Building not found with this room")
    camera = Camera(
        name=camera_data.name,
        description=camera_data.description,
        rtsp_url=camera_data.rtsp_url,
        vpn_rtsp_url=camera_data.vpn_rtsp_url,
        stream_url=camera_data.stream_url,
        username=camera_data.username,
        password=camera_data.password,
        latitude=camera_data.latitude,
        longitude=camera_data.longitude,
        altitude=camera_data.altitude,
        room_id=camera_data.room_id,
        tenant_id=tenant_id,
        ip_address=camera_data.ip_address,
        mac_address=camera_data.mac_address,
        tenant_entity_id=int(str(building.tenant_entity_id)),
        jetson_device_id=camera_data.jetson_device_id
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    if camera_data.snapshot_url:
        camera_snapshot = CameraSnapshot(
            camera_id=camera.id, snapshot_url=camera_data.snapshot_url, tenant_id=tenant_id
        )
        db.add(camera_snapshot)
        db.commit()
        db.refresh(camera_snapshot)
    return camera


def update_camera(db: Session, pk: int, camera_data: CameraBase, tenant_id: int):
    same_camera = (
        db.query(Camera).filter_by(tenant_id=tenant_id, room_id=camera_data.room_id, name=camera_data.name).first()
    )
    if same_camera and same_camera.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Camera with name {camera_data.name} already exists"
        )
    if not db.query(exists().where(and_(Room.id == camera_data.room_id, Room.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    camera = db.query(Camera).filter_by(id=pk, is_active=True).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera with id {pk} not found")
    if camera_data.name:
        camera.name = camera_data.name
    if camera_data.description:
        camera.description = camera_data.description
    if camera_data.rtsp_url:
        camera.rtsp_url = camera_data.rtsp_url
    if camera_data.vpn_rtsp_url:
        camera.vpn_rtsp_url = camera_data.vpn_rtsp_url
    if camera_data.stream_url:
        camera.stream_url = camera_data.stream_url
    if camera_data.username:
        camera.username = camera_data.username
    if camera_data.password:
        camera.password = camera_data.password
    if camera_data.latitude:
        camera.latitude = camera_data.latitude
    if camera_data.longitude:
        camera.longitude = camera_data.longitude
    if camera_data.altitude:
        camera.altitude = camera_data.altitude
    if camera_data.room_id:
        camera.room_id = camera_data.room_id
    if camera_data.jetson_device_id:
        camera.jetson_device_id = camera_data.jetson_device_id
    if camera_data.ip_address:
        camera_data.ip_address = camera_data.ip_address

    db.commit()
    db.refresh(camera)
    return camera


def delete_camera(db: Session, pk: int):
    camera = db.query(Camera).filter_by(id=pk, is_active=True).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera with id {pk} not found")
    camera.is_active = False
    db.commit()
    return camera


def get_cameras_by_user_permissions(db: Session, user, room_id: int, is_active: bool = True):
    tenant_entity = db.query(TenantEntity).filter_by(id=user.tenant_entity_id).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    cameras = (
        db.query(Camera)
        .filter_by(room_id=room_id, is_active=is_active)
        .join(Room)
        .join(Building)
        .join(TenantEntity)
        .filter(TenantEntity.hierarchy_level >= tenant_entity.hierarchy_level)
        .all()
    )
    return cameras
