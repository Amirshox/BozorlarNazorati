from fastapi import HTTPException, status
from sqlalchemy import and_, exists, select
from sqlalchemy.orm.session import Session

from models import Camera, Role, Tenant, TenantEntity, TenantProfile, User, UserSmartCamera
from schemas.user import UserBase, UserCreate, UserUpdate
from utils.generator import no_bcrypt

from .db_user_smart_camera import delete_user_smart_camera


def create_tenant_entity_user(db: Session, tenant_id: int, data: UserCreate):
    db_user = db.query(User).filter_by(email=data.email).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if not db.query(TenantEntity.id).filter_by(id=data.tenant_entity_id, is_active=True).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity does not exist")

    if not db.query(Role.id).filter_by(id=data.role_id, is_active=True).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role does not exist")

    db_user = User(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        password=no_bcrypt(data.password),
        phone=data.phone,
        photo=data.photo,
        user_group=data.user_group,
        role_id=data.role_id,
        embedding=data.embedding,
        cropped_image=data.cropped_image,
        embedding512=data.embedding512,
        cropped_image512=data.cropped_image512,
        pinfl=data.pinfl,
        tenant_id=tenant_id,
        tenant_entity_id=data.tenant_entity_id,
        pwd=data.password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def get_user_roles(db: Session, tenant_id: int):
    tenant = db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant_profile = db.query(TenantProfile).filter_by(id=tenant.tenant_profile_id).first()
    if not tenant_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant profile not found")
    return tenant_profile.roles


def create_inactive_tenant_entity_user(db: Session, tenant_id: int, data: UserBase):
    db_user = db.query(User).filter_by(email=data.email).first()
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    if not db.query(exists().where(and_(TenantEntity.id == data.tenant_entity_id, TenantEntity.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity does not exist")

    if not db.query(exists().where(and_(Role.id == data.role_id, Role.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role does not exist")
    db_user = User(
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        photo=data.photo,
        phone=data.phone,
        user_group=data.user_group,
        role_id=data.role_id,
        embedding=data.embedding,
        cropped_image=data.cropped_image,
        embedding512=data.embedding512,
        cropped_image512=data.cropped_image512,
        pinfl=data.pinfl,
        tenant_id=tenant_id,
        tenant_entity_id=data.tenant_entity_id,
        is_active=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


def get_tenant_entity_users(db: Session, tenant_id: int, tenant_entity_id: int, is_active: bool = True):
    return db.query(User).filter_by(tenant_id=tenant_id, tenant_entity_id=tenant_entity_id, is_active=is_active)


def get_users_by_scamera_id(db: Session, smart_camera_id: int, is_active: bool = True):
    subquery = (
        select(UserSmartCamera.user_id)
        .where(and_(UserSmartCamera.smart_camera_id == smart_camera_id, UserSmartCamera.is_active == is_active))
        .distinct()
    )
    return db.query(User).where(and_(User.id.in_(subquery), User.is_active == is_active))


def get_tenant_entity_user_by_email(db: Session, email: str):
    return db.query(User).filter_by(email=email).first()


def get_tenant_entity_user(db: Session, tenant_id: int, user_id: int, is_active: bool = True):
    return db.query(User).filter_by(tenant_id=tenant_id, id=user_id, is_active=is_active).first()


def get_tenant_users(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(User).filter_by(tenant_id=tenant_id, is_active=is_active)


def get_users_by_camera(db: Session, camera_id: int):
    return (
        db.query(User)
        .join(Camera, User.tenant_entity_id == Camera.tenant_entity_id)
        .filter(and_(Camera.id == camera_id, User.is_active))
    )


def update_tenant_user(db: Session, tenant_id: int, user_id: int, data: UserUpdate):
    exist_user = db.query(User).filter_by(email=data.email).first()
    if exist_user and exist_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    db_user = db.query(User).filter_by(tenant_id=tenant_id, id=user_id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not db.query(exists().where(and_(TenantEntity.id == data.tenant_entity_id, TenantEntity.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity does not exist")
    if not db.query(exists().where(and_(Role.id == data.role_id, Role.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role does not exist")
    if data.email:
        db_user.email = data.email
    if data.first_name:
        db_user.first_name = data.first_name
    if data.last_name:
        db_user.last_name = data.last_name
    if data.phone:
        db_user.phone = data.phone
    if data.photo:
        db_user.photo = data.photo
    if data.user_group:
        db_user.user_group = data.user_group
    if data.role_id:
        db_user.role_id = data.role_id
    if data.embedding:
        db_user.embedding = data.embedding
    if data.cropped_image:
        db_user.cropped_image = data.cropped_image
    if data.embedding512:
        db_user.embedding512 = data.embedding512
    if data.cropped_image512:
        db_user.cropped_image512 = data.cropped_image512
    if data.pinfl:
        db_user.pinfl = data.pinfl
    db.commit()
    db.refresh(db_user)

    user_scamera = db.query(UserSmartCamera).filter_by(user_id=user_id, is_active=True).all()
    if user_scamera:
        for u_scamera in user_scamera:
            u_scamera.needs_tobe_updated = True
            db.commit()
            db.refresh(u_scamera)
    return db_user


def set_password_and_activate(db: Session, user_id: int, new_password: str):
    db_user = db.query(User).filter_by(id=user_id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db_user.password = no_bcrypt(new_password)
    db_user.is_active = True
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_tenant_user(db: Session, tenant_id: int, user_id: int):
    user_scameras = db.query(UserSmartCamera).filter_by(user_id=user_id, is_active=True).all()
    for user_scamera in user_scameras:
        delete_user_smart_camera(db, int(str(user_scamera.id)))
    db_user = db.query(User).filter_by(tenant_id=tenant_id, id=user_id, is_active=True).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db_user.is_active = False
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_by_pinfl(db: Session, pinfl: str):
    return db.query(User).filter_by(pinfl=pinfl).first()
