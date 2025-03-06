from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import Role, TenantProfile
from schemas.role import RoleCreate, RoleUpdate


def get_roles(db: Session, is_active: bool = True):
    return db.query(Role).filter_by(is_active=is_active)


def get_role(db: Session, pk: int, is_active: bool = True):
    role = db.query(Role).filter_by(id=pk, is_active=is_active).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


def create_role(db: Session, role_data: RoleCreate):
    role_exists = db.query(Role).filter_by(name=role_data.name, tenant_profile_id=role_data.tenant_profile_id, is_active=True).first()
    if role_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")

    if not db.query(
        exists().where(and_(TenantProfile.id == role_data.tenant_profile_id, TenantProfile.is_active))
    ).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant profile does not exist")
    role = Role(name=role_data.name, description=role_data.description, tenant_profile_id=role_data.tenant_profile_id)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, pk: int, role_data: RoleUpdate):
    same_role = db.query(Role).filter_by(name=role_data.name).first()
    if same_role and same_role.id != pk:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    role = db.query(Role).filter_by(id=pk).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    if role_data.name:
        role.name = role_data.name
    if role_data.description:
        role.description = role_data.description
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, pk: int):
    role = db.query(Role).filter_by(id=pk, is_active=True).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    role.is_active = False
    db.commit()
    return role
