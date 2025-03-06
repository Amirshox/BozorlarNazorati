from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm.session import Session

from models import (
    Identity,
    IdentityRelative,
    Relative,
    TenantEntity,
)
from schemas.identity import RelativeBase


def create_relative(db: Session, data: RelativeBase):
    relative = Relative(**data.dict())
    db.add(relative)
    db.commit()
    db.refresh(relative)
    return relative


def get_relative_identities(db: Session, relative_id: int):
    return db.query(IdentityRelative).filter_by(relative_id=relative_id, is_active=True).all()


def get_relative_children(db: Session, relative_id: int):
    return (
        db.query(Identity)
        .join(IdentityRelative, IdentityRelative.identity_id == Identity.id)
        .filter(
            and_(
                IdentityRelative.relative_id == relative_id,
                Identity.is_active,
                IdentityRelative.is_active,
            )
        )
        .all()
    )


def get_relatives(db: Session):
    return db.query(Relative).filter_by(is_active=True)


def get_entity_relatives(db: Session, tenant_entity_id: int):
    return (
        db.query(Relative)
        .join(IdentityRelative, IdentityRelative.relative_id == Relative.id)
        .join(Identity, Identity.id == IdentityRelative.identity_id)
        .join(TenantEntity, TenantEntity.id == Identity.tenant_entity_id)
        .filter(
            and_(
                TenantEntity.id == tenant_entity_id,
                Relative.photo.is_(None),
                Relative.pinfl.is_not(None),
                Relative.is_active,
            )
        )
        .all()
    )


def get_uploadable_relatives(db: Session, tenant_entity_id: int):
    return (
        db.query(Relative)
        .join(IdentityRelative, IdentityRelative.relative_id == Relative.id)
        .join(Identity, Identity.id == IdentityRelative.identity_id)
        .join(TenantEntity, TenantEntity.id == Identity.tenant_entity_id)
        .filter(and_(TenantEntity.id == tenant_entity_id, Relative.photo.is_not(None), Relative.is_active))
        .all()
    )


def get_relative(db: Session, pk: int):
    relative = db.query(Relative).filter_by(id=pk, is_active=True).first()
    if not relative:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Relative not found")
    return relative


def get_relative_by_username(db: Session, username: str):
    return db.query(Relative).filter_by(username=username).first()


def update_relative(db: Session, pk: int, data: RelativeBase):
    relative = db.query(Relative).filter_by(id=pk, is_active=True).first()
    if not relative:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Relative not found")
    if data.first_name:
        relative.first_name = data.first_name
    if data.last_name:
        relative.last_name = data.last_name
    if data.photo:
        relative.photo = data.photo
    if data.email:
        relative.email = data.email
    if data.phone:
        relative.phone = data.phone
    if data.pinfl:
        relative.pinfl = data.pinfl
    db.commit()
    db.refresh(relative)
    return relative


def delete_relative(db: Session, pk: int):
    relative = db.query(Relative).filter_by(id=pk, is_active=True).first()
    if not relative:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Relative not found")
    relative.is_active = False
    db.commit()
    db.refresh(relative)
    return relative
