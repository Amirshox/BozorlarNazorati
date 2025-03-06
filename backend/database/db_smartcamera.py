from typing import List, Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import (
    Attendance,
    Building,
    ErrorSmartCamera,
    Firmware,
    Identity,
    Room,
    SmartCamera,
    SmartCameraProfile,
    SmartCameraSnapshot,
    SmartCameraTask,
    SmartCameraTaskUser,
    TenantEntity,
    User,
    VisitorAttendance,
    WantedAttendance,
)
from schemas.infrastructure import (
    FirmwareBase,
    FirmwareUpdate,
    SmartCameraBase,
    SmartCameraProfileBase,
)
from schemas.nvdsanalytics import ErrorSmartCameraBase


def super_get_smart_cameras(
    db: Session, _id: int, get_by: Literal["tenant", "entity", "building", "room"] = "entity", is_active: bool = True
):
    if get_by == "tenant":
        return db.query(SmartCamera).filter_by(tenant_id=_id, is_active=is_active)
    elif get_by == "entity":
        return db.query(SmartCamera).filter_by(tenant_entity_id=_id, is_active=is_active)
    elif get_by == "building":
        return db.query(SmartCamera).join(Room).filter(and_(Room.building_id == _id, SmartCamera.is_active))
    elif get_by == "room":
        return db.query(SmartCamera).filter_by(room_id=_id, is_active=is_active)
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Incorrect parameter -> 'get_by'")


def get_smart_cameras(db: Session, room_id: int, tenant_id: int, is_active: bool = True):
    return db.query(SmartCamera).filter_by(tenant_id=tenant_id, room_id=room_id, is_active=is_active)


def get_smart_cameras_for_health(db: Session, tenant_id: int = None):
    if tenant_id:
        return db.query(SmartCamera).filter_by(tenant_id=tenant_id, is_active=True).all()
    return db.query(SmartCamera).filter_by(is_active=True).all()


def get_smart_camera(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    camera = db.query(SmartCamera).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SmartCamera with id {pk} not found",
        )
    return camera


def get_smart_camera_for_3(db: Session, pk: int, is_active: bool = True):
    camera = db.query(SmartCamera).filter_by(id=pk, is_active=is_active).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SmartCamera with id {pk} not found",
        )
    return camera


def get_smart_cameras_for_map(
    db: Session,
    tenant_id: int,
    country_id: Optional[int] = None,
    region_id: Optional[int] = None,
    district_id: Optional[int] = None,
):
    smart_cameras = (
        db.query(SmartCamera.id, SmartCamera.tenant_id, SmartCamera.device_lat, SmartCamera.device_long)
        .join(TenantEntity)
        .filter(SmartCamera.is_active)
    )

    smart_cameras = smart_cameras.filter(TenantEntity.tenant_id == tenant_id)

    if country_id:
        smart_cameras = smart_cameras.filter(TenantEntity.country_id == country_id)

    if district_id:
        smart_cameras = smart_cameras.filter(TenantEntity.district_id == district_id)

    if region_id:
        smart_cameras = smart_cameras.filter(TenantEntity.region_id == region_id)

    return smart_cameras.all()


def create_smart_camera(db: Session, camera_data: SmartCameraBase, tenant_id: int, temp_password: str | None = None):
    exist_camera = (
        db.query(SmartCamera).filter_by(tenant_id=tenant_id, room_id=camera_data.room_id, name=camera_data.name).first()
    )
    if exist_camera:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SmartCamera with name {camera_data.name} already exists",
        )

    exists_device_id = (
        db.query(SmartCamera)
        .filter_by(device_id=camera_data.device_id, device_mac=camera_data.device_mac, is_active=True)
        .first()
    )
    if exists_device_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SmartCamera with device id and mac already exists",
        )
    building = (
        db.query(Building)
        .join(Room, Room.building_id == Building.id)
        .filter(
            and_(
                Room.id == camera_data.room_id,
                Room.is_active,
                Building.is_active,
            )
        )
        .first()
    )
    if not building:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Building not found with this room",
        )
    if not db.query(
        exists().where(
            and_(
                camera_data.smart_camera_profile_id == SmartCameraProfile.id,
                SmartCameraProfile.is_active,
            )
        )
    ).scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SmartCamera profile does not exist",
        )
    camera = SmartCamera(
        name=camera_data.name,
        device_id=camera_data.device_id,
        device_mac=camera_data.device_mac,
        lib_platform_version=camera_data.lib_platform_version,
        software_version=camera_data.software_version,
        lib_ai_version=camera_data.lib_ai_version,
        time_stamp=camera_data.time_stamp,
        device_name=camera_data.device_name,
        device_ip=camera_data.device_ip,
        device_lat=camera_data.device_lat,
        device_long=camera_data.device_long,
        stream_url=camera_data.stream_url,
        rtsp_url=camera_data.rtsp_url,
        username=camera_data.username,
        password=camera_data.password,
        room_id=camera_data.room_id,
        type=camera_data.type,
        tenant_id=tenant_id,
        tenant_entity_id=int(str(building.tenant_entity_id)),
        smart_camera_profile_id=camera_data.smart_camera_profile_id,
        temp_password=temp_password,
    )
    db.add(camera)
    db.commit()
    db.refresh(camera)
    return camera


def update_smart_camera(db: Session, pk: int, scamera: SmartCameraBase, tenant_id: int):
    same_camera = (
        db.query(SmartCamera).filter_by(tenant_id=tenant_id, room_id=scamera.room_id, name=scamera.name).first()
    )
    if same_camera and same_camera.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SmartCamera with name {scamera.name} already exists",
        )
    camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not camera:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SmartCamera with id {pk} not found",
        )

    if not db.query(exists().where(and_(scamera.room_id == Room.id, Room.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room does not exist")
    if not db.query(
        exists().where(
            and_(
                scamera.smart_camera_profile_id == SmartCameraProfile.id,
                SmartCameraProfile.is_active,
            )
        )
    ).scalar():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SmartCamera profile does not exist",
        )
    if scamera.name:
        camera.name = scamera.name
    if scamera.device_id:
        camera.device_id = scamera.device_id
    if scamera.device_mac:
        camera.device_mac = scamera.device_mac
    if scamera.lib_platform_version:
        camera.lib_platform_version = scamera.lib_platform_version
    if scamera.software_version:
        camera.software_version = scamera.software_version
    if scamera.lib_ai_version:
        camera.lib_ai_version = scamera.lib_ai_version
    if scamera.time_stamp:
        camera.time_stamp = scamera.time_stamp
    if scamera.device_name:
        camera.device_name = scamera.device_name
    if scamera.device_ip:
        camera.device_ip = scamera.device_ip
    if scamera.device_lat:
        camera.device_lat = scamera.device_lat
    if scamera.device_long:
        camera.device_long = scamera.device_long
    if scamera.stream_url:
        camera.stream_url = scamera.stream_url
    if scamera.rtsp_url:
        camera.rtsp_url = scamera.rtsp_url
    if scamera.username:
        camera.username = scamera.username
    if scamera.password:
        camera.password = scamera.password
    if scamera.room_id:
        camera.room_id = scamera.room_id
    if scamera.type:
        camera.type = scamera.type
    if scamera.smart_camera_profile_id:
        camera.smart_camera_profile_id = scamera.smart_camera_profile_id
    db.commit()
    db.refresh(camera)
    return camera


def delete_smart_camera(db: Session, pk: int):
    camera = db.query(SmartCamera).filter_by(id=pk, is_active=True).first()
    if not camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SmartCamera with id {pk} not found")
    camera.is_active = False
    db.commit()
    return camera


def get_user_attendances(
    db: Session,
    user_type: Literal["visitor", "identity", "wanted"],
    smart_camera_id: int,
    limit: int = None,
):
    smart_camera = db.query(SmartCamera).filter_by(id=smart_camera_id, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SmartCamera does not exist")
    model = None
    if user_type == "visitor":
        model = VisitorAttendance
    elif user_type == "identity":
        model = Attendance
    elif user_type == "wanted":
        model = WantedAttendance
    if limit:
        return (
            (db.query(model).filter_by(smart_camera_id=smart_camera_id).order_by(model.created_at.desc()).limit(limit))
            if model
            else None
        )
    return (
        (db.query(model).filter_by(smart_camera_id=smart_camera_id).order_by(model.created_at.desc()))
        if model
        else None
    )


def get_snapshots(db: Session, camera_id: int, tenant_id: int, limit: int = None):
    smart_camera = db.query(SmartCamera).filter_by(tenant_id=tenant_id, id=camera_id, is_active=True).first()
    if not smart_camera:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have no access to this SmartCamera",
        )
    if limit:
        return (
            db.query(SmartCameraSnapshot)
            .filter_by(smart_camera_id=camera_id, is_active=True)
            .order_by(SmartCameraSnapshot.created_at.desc())
            .limit(limit)
        )
    return (
        db.query(SmartCameraSnapshot)
        .filter_by(smart_camera_id=camera_id, is_active=True)
        .order_by(SmartCameraSnapshot.created_at.desc())
    )


def get_snapshots_for_3(db: Session, camera_id: int, tenant_ids: List[int], limit: int = None):
    smart_camera = db.query(SmartCamera).filter_by(id=camera_id, is_active=True).first()
    if not smart_camera:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SmartCamera not found")
    if smart_camera.tenant_id not in tenant_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission denied")
    if limit:
        return (
            db.query(SmartCameraSnapshot)
            .filter_by(smart_camera_id=camera_id, is_active=True)
            .order_by(SmartCameraSnapshot.created_at.desc())
            .limit(limit)
        )
    return (
        db.query(SmartCameraSnapshot)
        .filter_by(smart_camera_id=camera_id, is_active=True)
        .order_by(SmartCameraSnapshot.created_at.desc())
    )


def get_smart_cameras_by_user_permissions(db: Session, user, room_id: int, is_active: bool = True):
    tenant_entity = db.query(TenantEntity).filter_by(id=user.tenant_entity_id).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    return db.query(SmartCamera).filter_by(tenant_id=tenant_entity.tenant_id, room_id=room_id, is_active=is_active)


def get_errors_by_scamera(db: Session, smart_camera_id: int, is_active: bool = True):
    return db.query(ErrorSmartCamera).filter_by(smart_camera_id=smart_camera_id, is_active=is_active)


def get_errors_by_identity(db: Session, identity_id: int, is_active: bool = True):
    return db.query(ErrorSmartCamera).filter_by(identity_id=identity_id, is_active=is_active)


def get_errors_by_user(db: Session, user_id: int, is_active: bool = True):
    return db.query(ErrorSmartCamera).filter_by(user_id=user_id, is_active=is_active)


def get_error_smart_camera(db: Session, pk: int, is_active: bool = True):
    error = db.query(ErrorSmartCamera).filter_by(id=pk, is_active=is_active).first()
    if not error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Error SmartCamera not found with id={pk}")
    return error


def get_errors(db: Session, is_resolved: bool = False, is_active: bool = True):
    return db.query(ErrorSmartCamera).filter_by(is_resolved=is_resolved, is_active=is_active)


def update_error_scamera(db: Session, pk: int, data: ErrorSmartCameraBase):
    if data.identity_id:
        identity = db.query(Identity).filter_by(id=data.identity_id, is_active=True).first()
        if not identity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found")
    if data.user_id:
        user = db.query(User).filter_by(id=data.user_id, is_active=True).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    if data.smart_camera_id:
        smart_camera = db.query(SmartCamera).filter_by(id=data.smart_camera_id, is_active=True).first()
        if not smart_camera:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SmartCamera not found")
    error_smart_camera = db.query(ErrorSmartCamera).filter_by(id=pk, is_active=True).first()
    if not error_smart_camera:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ErrorSmartCamera not found")
    if data.identity_id:
        error_smart_camera.identity_id = data.identity_id
    if data.user_id:
        error_smart_camera.user_id = data.user_id
    if data.smart_camera_id:
        error_smart_camera.smart_camera_id = data.smart_camera_id
    if data.error_type:
        error_smart_camera.error_type = data.error_type
    if data.error_message:
        error_smart_camera.error_message = data.error_message
    if data.error_code:
        error_smart_camera.error_code = data.error_code
    if data.is_sent is not None:
        error_smart_camera.is_sent = data.is_sent
    if data.is_resolved is not None:
        error_smart_camera.is_resolved = data.is_resolved
    db.commit()
    db.refresh(error_smart_camera)
    return error_smart_camera


def delete_error_scamera(db: Session, pk: int):
    error_scamera = db.query(ErrorSmartCamera).filter_by(id=pk, is_active=True).first()
    if not error_scamera:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ErrorSmartCamera not found")
    error_scamera.is_active = False
    db.commit()
    db.refresh(error_scamera)
    return error_scamera


def get_scameras_by_profile(db: Session, profile_id: int):
    return db.query(SmartCamera).filter_by(smart_camera_profile_id=profile_id, is_active=True).all()


def create_profile(db: Session, tenant_id: int, data: SmartCameraProfileBase):
    exist_profile = db.query(SmartCameraProfile).filter_by(name=data.name, tenant_id=tenant_id, is_active=True).first()
    if exist_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile already exists")
    new_profile = SmartCameraProfile(name=data.name, description=data.description, tenant_id=tenant_id)
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile


def get_profile(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    profile = db.query(SmartCameraProfile).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


def get_profiles(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(SmartCameraProfile).filter_by(tenant_id=tenant_id, is_active=is_active).all()


def update_profile(db: Session, pk: int, tenant_id: int, data: SmartCameraProfileBase):
    same_profile = db.query(SmartCameraProfile).filter_by(name=data.name, tenant_id=tenant_id, is_active=True).first()
    if same_profile and same_profile.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Profile already exists with {data.name}",
        )
    old_profile = db.query(SmartCameraProfile).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not old_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    if data.name:
        old_profile.name = data.name
    if data.description:
        old_profile.description = data.description
    db.commit()
    db.refresh(old_profile)
    return old_profile


def delete_profile(db: Session, pk: int, tenant_id: int):
    profile = db.query(SmartCameraProfile).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    profile.is_active = False
    db.commit()
    db.refresh(profile)
    return profile


def create_firmware(db: Session, tenant_id: int, data: FirmwareBase):
    exist_firmware = db.query(Firmware).filter_by(name=data.name, tenant_id=tenant_id, is_active=True).first()
    if exist_firmware:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firmware already exists")
    new_firmware = Firmware(name=data.name, description=data.description, img=data.img, tenant_id=tenant_id)
    db.add(new_firmware)
    db.commit()
    db.refresh(new_firmware)
    return new_firmware


def get_firmware(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    firmware = db.query(Firmware).filter_by(id=pk, tenant_id=tenant_id, is_active=is_active).first()
    if not firmware:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware not found")
    return firmware


def get_firmwares(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(Firmware).filter_by(tenant_id=tenant_id, is_active=is_active).all()


def update_firmware(db: Session, pk: int, tenant_id: int, data: FirmwareUpdate):
    same_firmware = db.query(Firmware).filter_by(name=data.name, tenant_id=tenant_id, is_active=True).first()
    if same_firmware and same_firmware.id != pk:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firmware already exists")
    old_firmware = db.query(Firmware).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not old_firmware:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware not found")
    old_firmware.name = data.name
    if data.description:
        old_firmware.description = data.description
    db.commit()
    db.refresh(old_firmware)
    return old_firmware


def delete_firmware(db: Session, pk: int, tenant_id: int):
    firmware = db.query(Firmware).filter_by(id=pk, tenant_id=tenant_id, is_active=True).first()
    if not firmware:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firmware not found")
    firmware.is_active = False
    db.commit()
    db.refresh(firmware)
    return firmware


def create_task_to_scamera(db: Session, task_type: str, smart_camera_id: int, user_id: int, user_type: str):
    new_task = SmartCameraTask(task_type=task_type, smart_camera_id=smart_camera_id)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    if user_type == "identity":
        new_task_user = SmartCameraTaskUser(task_id=new_task.id, identity_id=user_id)
    elif user_type == "visitor":
        new_task_user = SmartCameraTaskUser(task_id=new_task.id, visitor_id=user_id)
    elif user_type == "relative":
        new_task_user = SmartCameraTaskUser(task_id=new_task.id, relative_id=user_id)
    elif user_type == "wanted":
        new_task_user = SmartCameraTaskUser(task_id=new_task.id, wanted_id=user_id)
    else:
        new_task_user = None
        print(f"unknown user_type: {user_type}")
    if new_task_user:
        db.add(new_task_user)
        db.commit()
        db.refresh(new_task_user)
