import json
import logging
import os
from typing import Literal

import requests
from fastapi import HTTPException, status
from sqlalchemy import and_, exists, update
from sqlalchemy.orm.session import Session

from models import (
    Camera,
    JetsonDevice,
    JetsonDeviceProfileAssociation,
    JetsonProfile,
    Room,
    Building
)
from schemas.infrastructure import JetsonBase, JetsonProfileUpdate
from utils.generator import no_bcrypt
from utils.log import timeit

HLS_SERVER = os.getenv("HLS_SERVER", "localhost")
SRS_SERVER = os.getenv("SRS_SERVER", "localhost")
logger = logging.getLogger(__name__)


def get_jetson_devices(db: Session, tenant_id: int, room_id: int = None, is_active: bool = True):
    if room_id:
        room = db.query(Room).filter_by(id=room_id, is_active=True).first()
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        return db.query(JetsonDevice).filter_by(tenant_id=tenant_id, room_id=room_id, is_active=is_active)
    return db.query(JetsonDevice).filter_by(tenant_id=tenant_id, is_active=is_active)

def get_jetson_devices_unsafe(db: Session, room_id: int = None, is_active: bool = True):
    if room_id:
        room = db.query(Room).filter_by(id=room_id, is_active=True).first()
        if not room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
        return db.query(JetsonDevice).filter_by(room_id=room_id, is_active=is_active)
    return db.query(JetsonDevice).filter_by(is_active=is_active)

async def get_jetson_device(db: Session, mongodb, pk: int, tenant_id: int | None, is_active: bool = True):
    if tenant_id is not None:
        jetson = db.query(JetsonDevice).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    else:
        jetson = db.query(JetsonDevice).filter_by(id=pk, is_active=is_active).first()

    if not jetson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Jetson Device with primary id {pk} not found"
        )
    jetson_status_revision = (
        await mongodb["status_revision"]
        .find({"jetson_device_id": jetson.device_id})
        .sort({"created_at": -1})
        .limit(1)
        .to_list(length=1)
    )

    if len(jetson_status_revision) > 0:
        jetson_status_revision = jetson_status_revision[0]

    return {
        "username": jetson.username,
        "password": jetson.password,
        "device_name": jetson.device_name,
        "device_id": jetson.device_id,
        "device_ip_vpn": jetson.device_ip_vpn,
        "device_stream_url": jetson.device_stream_url,
        "room_id": jetson.room_id,
        "id": jetson.id,
        "created_at": jetson.created_at,
        "updated_at": jetson.updated_at,
        "status_revision": None
        if not jetson_status_revision
        else {
            "id": str(jetson_status_revision["_id"]),
            "created_at": jetson_status_revision["created_at"],
            "status_description": jetson_status_revision["status_description"],
        },
    }


@timeit
def create_jetson_device(db: Session, jetson_data: JetsonBase, tenant_id: int):
    existing_jetson = (
        db.query(JetsonDevice).filter_by(tenant_id=tenant_id, device_id=jetson_data.device_id, is_active=True).first()
    )
    if existing_jetson:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Jetson Device with device Id {existing_jetson.device_id} already exists",
        )
    if not db.query(exists().where(and_(Room.id == jetson_data.room_id, Room.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    jetson = JetsonDevice(
        username=jetson_data.username,
        password=jetson_data.password,
        device_name=jetson_data.device_name,
        device_id=jetson_data.device_id,
        device_ip_vpn=jetson_data.device_ip_vpn,
        device_stream_url=jetson_data.device_stream_url,
        room_id=jetson_data.room_id,
        tenant_id=tenant_id,
    )
    db.add(jetson)
    db.commit()
    db.refresh(jetson)
    try:
        data = {"uri": jetson.device_ip_vpn, "alias": f"jetson{jetson.id}"}
        response = requests.post(HLS_SERVER + "/start", json=data)
        if response.status_code == 200:
            response = json.loads(response.text)
            jetson.device_stream_url = HLS_SERVER + response.get("uri", None)
            db.commit()
            db.refresh(jetson)
    except Exception as e:
        logging.error(f"Error while taking hls url out of device vpn ip, error: {e}")
    return jetson


@timeit
def update_jetson_device(db: Session, pk, jetson_data: JetsonBase, tenant_id: int):
    existing_jetson = db.query(JetsonDevice).filter_by(tenant_id=tenant_id, device_id=jetson_data.device_id).first()
    if existing_jetson and existing_jetson.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Jetson Device with device Id {existing_jetson.device_id} already exists",
        )
    room = db.query(Room).filter_by(id=jetson_data.room_id, tenant_id=tenant_id, is_active=True).first()
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    jetson = db.query(JetsonDevice).filter_by(id=pk, tenant_id=tenant_id).first()
    if not jetson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Jetson Device with primary id {pk} not found"
        )
    if jetson_data.username:
        jetson.username = jetson_data.username
    if jetson_data.password:
        jetson.password = jetson_data.password
    if jetson_data.device_name:
        jetson.device_name = jetson_data.device_name
    if jetson_data.device_id:
        jetson.device_id = jetson_data.device_id
    if jetson_data.device_ip_vpn:
        jetson.device_ip_vpn = jetson_data.device_ip_vpn
    if jetson_data.device_stream_url:
        jetson.device_stream_url = jetson_data.device_stream_url
    if jetson_data.room_id:
        jetson.room_id = jetson_data.room_id
    db.add(jetson)
    db.commit()
    db.refresh(jetson)
    try:
        data = {"uri": jetson.device_ip_vpn, "alias": f"jetson{jetson.id}"}
        response = requests.post(HLS_SERVER + "/start", json=data)
        if response.status_code == 200:
            response = json.loads(response.text)
            jetson.device_stream_url = HLS_SERVER + response.get("uri", None)
            db.commit()
            db.refresh(jetson)
    except Exception as e:
        logging.error(f"Error while taking hls url out of device vpn ip, error: {e}")
    return jetson


def delete_jetson_device(db: Session, pk: int, tenant_id: int):
    jetson = db.query(JetsonDevice).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not jetson:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Jetson Device with primary id {pk} not found"
        )
    jetson.is_active = False
    db.commit()
    db.refresh(jetson)
    return jetson


def get_jetson_cameras(db: Session, pk: int):
    jetson = db.query(JetsonDevice).filter_by(id=pk, is_active=True).first()
    if not jetson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jetson device not found")
    
    return db.query(Camera).filter_by(jetson_device_id=pk).all()


def create_jetson_profile(
    db: Session,
    name: str,
    username: str,
    password: str,
    cuda_version: str,
    deepstream_version: str,
    jetpack_version: str,
):
    existing_jetson_profile = db.query(JetsonProfile).filter_by(username=username).first()

    if existing_jetson_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"Jetson profile with username({username}) already exists!"
        )

    created_jetson_profile = JetsonProfile(
        name=name,
        username=username,
        password=no_bcrypt(password),
        cuda_version=cuda_version,
        deepstream_version=deepstream_version,
        jetpack_version=jetpack_version,
    )

    db.add(created_jetson_profile)
    db.commit()
    db.refresh(created_jetson_profile)
    return created_jetson_profile


def update_jetson_profile(db: Session, jetson_profile_id: int, jetson_optional_details: JetsonProfileUpdate):
    updating_details = {key: value for key, value in jetson_optional_details.__dict__.items() if value is not None}
    execution_result = db.execute(
        update(JetsonProfile).where(JetsonProfile.id == jetson_profile_id).values(**updating_details)
    )
    db.commit()
    return execution_result


def delete_jetson_profile(db: Session, jetson_profile_id: int):
    current_jetson_profile = db.query(JetsonProfile).filter_by(id=jetson_profile_id).first()

    if not current_jetson_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jetson profile with specified id({jetson_profile_id}) not found!",
        )
    jetson_device_profile_associations = (
        db.query(JetsonDeviceProfileAssociation).filter_by(jetson_profile_id=jetson_profile_id).all()
    )

    for each_association in jetson_device_profile_associations:
        db.delete(each_association)
    db.commit()
    db.delete(current_jetson_profile)
    db.commit()
    return current_jetson_profile


def jetson_profile_register_device(db: Session, jetson_profile_id: int, jetson_device_id: int):
    current_jetson_profile = db.query(JetsonProfile).filter_by(id=jetson_profile_id).first()
    current_jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not current_jetson_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jetson profile with specified id ({jetson_profile_id}) not found!",
        )
    if not current_jetson_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jetson device with specified id ({jetson_device_id}) not found!",
        )

    existing_jetson_profile = (
        db.query(JetsonDeviceProfileAssociation).filter_by(jetson_device_id=jetson_device_id).first()
    )

    if existing_jetson_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Jetson device with id ({jetson_device_id}) has already been registered to profile!",
        )
    created_association = JetsonDeviceProfileAssociation(
        jetson_device_id=jetson_device_id, jetson_profile_id=jetson_profile_id
    )
    db.add(created_association)
    db.commit()
    db.refresh(created_association)

    return created_association


def get_jetson_profile_by_profile(db: Session, profile_id: int):
    current_jetson_profile = db.query(JetsonProfile).filter_by(id=profile_id).first()

    if not current_jetson_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Jetson profile with specified  id ({profile_id}) not found!"
        )
    return current_jetson_profile


def get_jetson_profiles(db: Session):
    return db.query(JetsonProfile).filter_by(is_active=True)


def get_jetson_profile_by_device(db: Session, device_id: int):
    current_jetson_device = db.query(JetsonDevice).filter_by(id=device_id).first()
    if not current_jetson_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Jetson profile with specified id ({device_id}) not found!"
        )
    associaton_jetson_device_profile = (
        db.query(JetsonDeviceProfileAssociation).filter_by(jetson_device_id=current_jetson_device.id).first()
    )
    jetson_profile = db.query(JetsonProfile).filter_by(id=associaton_jetson_device_profile.jetson_profile_id).first()
    if not jetson_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jetson profile with id ({associaton_jetson_device_profile.jetson_profile_id}) not found!",
        )
    return jetson_profile


def get_jetson_profile_by_username(db: Session, profile_username: str):
    return db.query(JetsonProfile).filter_by(username=profile_username).first()

def get_jetson_device_by_id(db: Session, device_id: str):
    return db.query(JetsonDevice).filter_by(device_id=device_id).first()

def get_jetson_device_for_stream(db: Session, pk: int):
    return db.query(JetsonDevice).filter_by(id=pk).first()

def get_jetson_device_by_building(db: Session, building_id: int, is_active: bool = True):
    current_building = db.query(Building).filter_by(id=building_id).first()

    if not current_building:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Building not found",
        )
    
    all_jetson_devices = []
    building_rooms = db.query(Room).filter_by(building_id=current_building.id).all()

    for each_room in building_rooms:
        current_jetson_devices = db.query(JetsonDevice).filter_by(room_id=each_room.id, is_active=is_active).all()
        all_jetson_devices.extend(current_jetson_devices)

    return all_jetson_devices

