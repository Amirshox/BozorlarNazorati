from datetime import datetime
from typing import Optional, Type

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, select
from sqlalchemy.orm.session import Session

from models import (
    ExtraAttendance,
    Identity,
    IdentityPhoto,
    IdentitySmartCamera,
    TenantEntity,
)
from models.identity import Package
from schemas.identity import IdentityCreate, IdentityUpdate
from services.face_auth import verify_insight_face_async
from tasks import send_updated_identity_photo_task
from utils.image_processing import extract_minio_url
from utils.kindergarten import get_birth_date_from_pinfl


def upload_identity_photo_to_platon(identity: Type[Identity], photo_pk: int, username: Optional[str] = None):
    message_data = {
        "tenant_id": identity.tenant_id,
        "mtt_id": identity.tenant_entity.external_id,
        "_id": identity.external_id,
        "identity_group": identity.identity_group,
        "photo_url": identity.photo,
        "photo_pk": photo_pk,
        "username": username,
    }
    send_updated_identity_photo_task.delay(message_data)


def create_identity(
    db: Session,
    tenant_id,
    identity_data: IdentityCreate,
    recieved_photo_url: str = None,
    username: Optional[str] = None,
):
    if not db.query(
        exists().where(and_(TenantEntity.id == identity_data.tenant_entity_id, TenantEntity.is_active))
    ).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")

    duplicate_identity = (
        db.query(Identity)
        .filter_by(
            tenant_id=tenant_id,
            tenant_entity_id=identity_data.tenant_entity_id,
            identity_group=identity_data.identity_group,
            external_id=identity_data.external_id,
            is_active=True,
        )
        .first()
    )
    if duplicate_identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity already exists with given data")

    bucket_name, object_name = extract_minio_url(url=identity_data.photo) if identity_data.photo else (None, None)

    identity = Identity(
        first_name=identity_data.first_name,
        last_name=identity_data.last_name,
        photo=identity_data.photo,
        email=identity_data.email,
        phone=identity_data.phone,
        pinfl=identity_data.pinfl,
        identity_group=identity_data.identity_group,
        identity_type=identity_data.identity_type,
        tenant_id=tenant_id,
        tenant_entity_id=identity_data.tenant_entity_id,
        left_side_photo=identity_data.left_side_photo,
        right_side_photo=identity_data.right_side_photo,
        top_side_photo=identity_data.top_side_photo,
        recieved_photo_url=recieved_photo_url,
        embedding=identity_data.embedding,
        cropped_image=identity_data.cropped_image,
        embedding512=identity_data.embedding512,
        cropped_image512=identity_data.cropped_image512,
        external_id=identity_data.external_id,
        group_id=identity_data.group_id,
        group_name=identity_data.group_name,
        bucket_name=bucket_name,
        object_name=object_name,
        i_embedding512=identity_data.i_embedding512,
        i_cropped_image512=identity_data.i_cropped_image512,
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    if identity_data.photo:
        new_identity_photo = IdentityPhoto(
            identity_id=identity.id,
            url=identity_data.photo,
            embedding=identity_data.embedding,
            cropped_image=identity_data.cropped_image,
            embedding512=identity_data.embedding512,
            cropped_image512=identity_data.cropped_image512,
            i_embedding512=identity_data.i_embedding512,
            i_cropped_image512=identity_data.i_cropped_image512,
            version=identity.version,
        )
        db.add(new_identity_photo)
        db.commit()
        db.refresh(new_identity_photo)
        if identity.tenant_id in [1, 18]:
            upload_identity_photo_to_platon(identity, photo_pk=new_identity_photo.id, username=username)
    return identity


def get_identities(
    db: Session,
    tenant_id: int,
    tenant_entity_id: int = None,
    is_active: bool = True,
    identity_type: str = None,
    identity_group: int = None,
    version: int = None,
    group_id: int = None,
    search: str = None,
):
    try:
        query = db.query(Identity).filter_by(tenant_id=tenant_id, deleted=False, is_active=is_active)
        if tenant_entity_id:
            query = query.filter_by(tenant_entity_id=tenant_entity_id)
        if identity_type:
            query = query.filter_by(identity_type=identity_type)
        if identity_group is not None:
            query = query.filter_by(identity_group=identity_group)
        if version:
            query = query.filter_by(version=version)
        if group_id:
            query = query.filter_by(group_id=group_id)
        if search:
            query = query.filter(
                Identity.first_name.ilike(f"%{search}%")
                | Identity.last_name.ilike(f"%{search}%")
                | Identity.pinfl.ilike(f"%{search}%")
                | Identity.external_id.ilike(f"%{search}%")
            )
    except Exception as e:
        print(e)
        query = db.query(Identity).filter_by(tenant_id=tenant_id, is_active=is_active)
    return query


def get_identities_by_entity_id(db: Session, tenant_entity_id: int, is_active: bool = True):
    return db.query(Identity).filter_by(tenant_entity_id=tenant_entity_id, deleted=False, is_active=is_active)


def get_identieis_by_jetson_id(db: Session, jetson_device_id: int, is_active: bool = True):
    return db.query(Identity).filter_by(jetson_device_id=jetson_device_id, deleted=False, is_active=is_active)


def get_identities_by_scamera_id(db: Session, smart_camera_id: int, is_active: bool = True):
    subquery = (
        select(IdentitySmartCamera.identity_id)
        .where(and_(IdentitySmartCamera.smart_camera_id == smart_camera_id, IdentitySmartCamera.is_active == is_active))
        .distinct()
    )
    return db.query(Identity).where(
        and_(Identity.id.in_(subquery), Identity.is_active == is_active, Identity.deleted.is_(False))
    )


def get_identities_by_type(db: Session, tenant_id: int, identity_type: str, is_active: bool = True):
    return db.query(Identity).filter_by(tenant_id=tenant_id, deleted=False, type=identity_type, is_active=is_active)


def get_identity_photo_history(db: Session, pk: int):
    return (
        db.query(IdentityPhoto)
        .filter_by(identity_id=pk, is_active=True)
        .order_by(IdentityPhoto.created_at.desc())
        .all()
    )


def get_identity_by_pinfl(db: Session, tenant_id: int, pinfl: str, is_active: bool = True):
    return db.query(Identity).filter_by(tenant_id=tenant_id, pinfl=pinfl, is_active=is_active).first()


def get_identity(db: Session, tenant_id, pk: int, is_active: bool = True):
    return db.query(Identity).filter_by(tenant_id=tenant_id, id=pk, is_active=is_active).first()


def update_identity(db: Session, tenant_id, pk: int, identity_data: IdentityUpdate, username: Optional[str] = None):
    identity = db.query(Identity).filter_by(tenant_id=tenant_id, id=pk).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    duplicate_identity = (
        db.query(Identity)
        .filter_by(
            tenant_id=tenant_id,
            tenant_entity_id=identity.tenant_entity_id,
            identity_group=identity_data.identity_group,
            external_id=identity_data.external_id,
            # is_active=True,
        )
        .first()
    )
    if duplicate_identity and duplicate_identity.id != pk:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity already exists")

    bucket_name, object_name = extract_minio_url(url=identity_data.photo) if identity_data.photo else (None, None)

    if identity_data.first_name:
        identity.first_name = identity_data.first_name
    if identity_data.last_name:
        identity.last_name = identity_data.last_name
    if identity_data.embedding512:
        identity.embedding512 = identity_data.embedding512
    if identity_data.email:
        identity.email = identity_data.email
    if identity_data.phone:
        identity.phone = identity_data.phone
    if identity_data.identity_group is not None:
        identity.identity_group = identity_data.identity_group
    if identity_data.identity_type:
        identity.identity_type = identity_data.identity_type
    if identity_data.left_side_photo:
        identity.left_side_photo = identity_data.left_side_photo
    if identity_data.right_side_photo:
        identity.right_side_photo = identity_data.right_side_photo
    if identity_data.top_side_photo:
        identity.top_side_photo = identity_data.top_side_photo
    if identity_data.embedding:
        identity.embedding = identity_data.embedding
    if identity_data.cropped_image:
        identity.cropped_image = identity_data.cropped_image
    if identity_data.cropped_image512:
        identity.cropped_image512 = identity_data.cropped_image512
    if identity_data.external_id:
        identity.external_id = identity_data.external_id
    if identity_data.jetson_device_id:
        identity.jetson_device_id = identity_data.jetson_device_id
    if identity_data.group_id:
        identity.group_id = identity_data.group_id
    if identity_data.group_name:
        identity.group_name = identity_data.group_name
    if bucket_name:
        identity.bucket_name = bucket_name
    if object_name:
        identity.object_name = object_name
    if identity_data.i_embedding512:
        identity.i_embedding512 = identity_data.i_embedding512
    if identity_data.i_cropped_image512:
        identity.i_cropped_image512 = identity_data.i_cropped_image512
    identity.version += 1
    if identity_data.photo and identity_data.photo != identity.photo:
        identity.photo = identity_data.photo
        new_identity_photo = IdentityPhoto(
            identity_id=pk,
            url=identity_data.photo,
            embedding=identity_data.embedding,
            cropped_image=identity_data.cropped_image,
            embedding512=identity_data.embedding512,
            cropped_image512=identity_data.cropped_image512,
            i_embedding512=identity_data.i_embedding512,
            i_cropped_image512=identity_data.i_cropped_image512,
            version=identity.version,
        )
        db.add(new_identity_photo)
        db.commit()
        db.refresh(new_identity_photo)
        if identity.labeling_status == 2:
            identity.labeling_status = 3
        if identity.tenant_id in [1, 18]:
            upload_identity_photo_to_platon(identity, photo_pk=new_identity_photo.id, username=username)
        if identity.identity_group == 1 and identity.pinfl and identity.tenant_id in [1, 18]:
            birth_date = get_birth_date_from_pinfl(identity.pinfl)
            verify_insight_face_async(
                new_identity_photo.id, identity.pinfl, datetime.fromisoformat(birth_date), identity.photo
            )
    identity.is_active = True
    db.commit()
    db.refresh(identity)

    identity_scamera = db.query(IdentitySmartCamera).filter_by(identity_id=pk, is_active=True).all()
    if identity_scamera:
        for i_scamera in identity_scamera:
            i_scamera.needs_tobe_updated = True
            db.commit()
            db.refresh(i_scamera)
    return identity


def delete_identity(db: Session, pk: int):
    identity = db.query(Identity).filter_by(id=pk, is_active=True).first()
    if not identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    identity.is_active = False
    identity.version += 1
    db.commit()
    db.refresh(identity)
    if identity.photos:
        for photo in identity.photos:
            photo.is_active = False
            db.commit()
            db.refresh(photo)
    return identity


def delete_extra_attendances(db: Session, identity_id: int):
    db.query(ExtraAttendance).filter_by(identity_id=identity_id, is_active=True).delete()
    db.commit()


def get_package_by_uuid(db: Session, uuid: str):
    return db.query(Package).filter_by(uuid=uuid, is_active=True).first()
