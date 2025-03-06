from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import Tenant, TenantEntity, Wanted
from schemas.wanted import WantedBase, WantedUpdate


def create_wanted(db: Session, data: WantedBase):
    if data.tenant_entity_id and not db.query(TenantEntity).filter_by(id=data.tenant_entity_id, is_active=True).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    wanted = Wanted(
        first_name=data.first_name,
        last_name=data.last_name,
        photo=data.photo,
        phone=data.phone,
        pinfl=data.pinfl,
        concern_level=data.concern_level,
        accusation=data.accusation,
        description=data.description,
        tenant_entity_id=data.tenant_entity_id,
    )
    db.add(wanted)
    db.commit()
    db.refresh(wanted)
    return wanted


def get_wanteds(db: Session, tenant_id: Optional[int] = None):
    if tenant_id:
        return db.query(Wanted).filter_by(tenant_id=tenant_id, is_active=True)
    return db.query(Wanted).filter_by(is_active=True)


def get_entity_wanteds(db: Session, tenant_entity_id: int, tenant_id: int):
    return db.query(Wanted).filter_by(tenant_id=tenant_id, tenant_entity_id=tenant_entity_id, is_active=True)


def get_wanted(db: Session, pk: int):
    wanted = db.query(Wanted).filter_by(id=pk, is_active=True).first()
    if not wanted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wanted not found")
    return wanted


def update_wanted(db: Session, pk: int, data: WantedUpdate):
    if data.tenant_entity_id and not db.query(TenantEntity).filter_by(id=data.tenant_entity_id, is_active=True).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
    if data.tenant_id and not db.query(Tenant).filter_by(id=data.tenant_id, is_active=True).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    wanted = db.query(Wanted).filter_by(id=pk, is_active=True).first()
    if data.first_name:
        wanted.first_name = data.first_name
    if data.last_name:
        wanted.last_name = data.last_name
    if data.photo:
        wanted.photo = data.photo
    if data.phone:
        wanted.phone = data.phone
    if data.pinfl:
        wanted.pinfl = data.pinfl
    if data.concern_level:
        wanted.concern_level = data.concern_level
    if data.accusation:
        wanted.accusation = data.accusation
    if data.description:
        wanted.description = data.description
    if data.tenant_id:
        wanted.tenant_id = data.tenant_id
    if data.tenant_entity_id:
        wanted.tenant_entity_id = data.tenant_entity_id
    db.commit()
    db.refresh(wanted)
    return wanted


def delete_wanted(db: Session, pk: int):
    wanted = db.query(Wanted).filter_by(id=pk, is_active=True).first()
    if not wanted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wanted not found")
    return wanted
