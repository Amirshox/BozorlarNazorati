from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import Tenant, TenantAdmin
from schemas.tenant_admin import (
    TenantAdminBaseInActive,
    TenantAdminCreate,
    TenantAdminUpdate,
)
from utils.generator import no_bcrypt


def get_tenant_admin_by_id(db: Session, pk: int, is_active: bool = True):
    return db.query(TenantAdmin).filter_by(id=pk, is_active=is_active).first()


def get_tenant_admin_by_email(db: Session, email: str):
    return db.query(TenantAdmin).filter_by(email=email, is_active=True).first()


def get_tenant_admins(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(TenantAdmin).filter_by(tenant_id=tenant_id, is_active=is_active)


def create_tenant_admin(db: Session, tenant_admin: TenantAdminCreate):
    exist_tenant_admin = (
        db.query(TenantAdmin).filter_by(tenant_id=tenant_admin.tenant_id, email=tenant_admin.email).first()
    )
    if exist_tenant_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant admin already exists")

    if not db.query(exists().where(and_(Tenant.id == tenant_admin.tenant_id, Tenant.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant does not exist")
    db_tenant_admin = TenantAdmin(
        first_name=tenant_admin.first_name,
        last_name=tenant_admin.last_name,
        email=tenant_admin.email,
        phone=tenant_admin.phone,
        password=no_bcrypt(tenant_admin.password),
        photo=tenant_admin.photo,
        tenant_id=tenant_admin.tenant_id,
    )
    db.add(db_tenant_admin)
    db.commit()
    db.refresh(db_tenant_admin)
    return db_tenant_admin


def create_inactive_tenant_admin(db: Session, tenant_admin: TenantAdminBaseInActive):
    exist = db.query(TenantAdmin).filter_by(tenant_id=tenant_admin.tenant_id, email=tenant_admin.email).first()
    if exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant admin already exists")
    if not db.query(exists().where(and_(Tenant.id == tenant_admin.tenant_id, Tenant.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant does not exist")

    db_tenant_admin = TenantAdmin(
        first_name=tenant_admin.first_name,
        last_name=tenant_admin.last_name,
        email=tenant_admin.email,
        phone=tenant_admin.phone,
        photo=tenant_admin.photo,
        tenant_id=tenant_admin.tenant_id,
        is_active=False,
    )
    db.add(db_tenant_admin)
    db.commit()
    db.refresh(db_tenant_admin)

    return db_tenant_admin


def update_tenant_admin(db: Session, pk: int, tenant_admin: TenantAdminUpdate):
    same_email_tenant_id_admin = (
        db.query(TenantAdmin).filter_by(tenant_id=tenant_admin.tenant_id, email=tenant_admin.email).first()
    )
    if same_email_tenant_id_admin and same_email_tenant_id_admin.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can not update Tenant admin with "
            f"tenant_id={tenant_admin.tenant_id} and email={tenant_admin.email}",
        )
    new_tenant_admin = db.query(TenantAdmin).filter_by(id=pk).first()
    if not new_tenant_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Admin not found")

    if not db.query(exists().where(and_(Tenant.id == tenant_admin.tenant_id, Tenant.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant_admin.first_name:
        new_tenant_admin.first_name = tenant_admin.first_name
    if tenant_admin.last_name:
        new_tenant_admin.last_name = tenant_admin.last_name
    if tenant_admin.email:
        new_tenant_admin.email = tenant_admin.email
    if tenant_admin.phone:
        new_tenant_admin.phone = tenant_admin.phone
    if tenant_admin.photo:
        new_tenant_admin.photo = tenant_admin.photo
    if tenant_admin.tenant_id:
        new_tenant_admin.tenant_id = tenant_admin.tenant_id
    db.commit()
    db.refresh(new_tenant_admin)

    return new_tenant_admin


def set_password_and_activate(db: Session, tenant_admin_id: int, password: str):
    db_tenant_admin = db.query(TenantAdmin).filter_by(id=tenant_admin_id).first()
    if not db_tenant_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Admin not found")
    db_tenant_admin.password = no_bcrypt(password)
    db_tenant_admin.is_active = True
    db.commit()
    db.refresh(db_tenant_admin)
    return db_tenant_admin


def delete_tenant_admin(db: Session, pk: int):
    db_tenant_admin = db.query(TenantAdmin).filter_by(id=pk, is_active=True).first()
    if not db_tenant_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Admin not found or inactive")
    db_tenant_admin.is_active = False
    db.commit()
    return db_tenant_admin

