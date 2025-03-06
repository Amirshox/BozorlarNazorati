from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import Module, TenantProfile, TenantProfileModule
from schemas.tenant_profile import (
    TenantProfileCreate,
    TenantProfileModuleCreate,
    TenantProfileModuleList,
    TenantProfileUpdate,
)


def get_tenant_profiles(db: Session, is_active: bool = True, query: Optional[str] = None):
    if query:
        tenant_profiles = (
            db.query(TenantProfile).filter_by(is_active=is_active).filter(TenantProfile.name.ilike(f"%{query}%"))
        )
    else:
        tenant_profiles = db.query(TenantProfile).filter_by(is_active=is_active)
    return tenant_profiles


def get_tenant_profile(db: Session, pk: int, is_active: bool = True):
    return db.query(TenantProfile).filter_by(id=pk, is_active=is_active).first()


def create_tenant_profile(db: Session, tenant_profile_data: TenantProfileCreate):
    tenant_profile_exists = db.query(TenantProfile).filter_by(name=tenant_profile_data.name).first()
    if tenant_profile_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant Profile already exists")
    tenant_profile = TenantProfile(name=tenant_profile_data.name, description=tenant_profile_data.description)
    db.add(tenant_profile)
    db.commit()
    return tenant_profile


def update_tenant_profile(db: Session, pk: int, tenant_profile_data: TenantProfileUpdate):
    deleted_profile = db.query(TenantProfile).filter_by(name=tenant_profile_data.name).first()
    if deleted_profile and deleted_profile.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can not update Tenant Profile with name {tenant_profile_data.name}",
        )
    tenant_profile = db.query(TenantProfile).filter_by(id=pk).first()
    if not tenant_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Profile not found")
    tenant_profile.name = tenant_profile_data.name
    if tenant_profile_data.description:
        tenant_profile.description = tenant_profile_data.description
    db.commit()
    db.refresh(tenant_profile)
    return tenant_profile


def delete_tenant_profile(db: Session, pk: int):
    tenant_profile = db.query(TenantProfile).filter_by(id=pk, is_active=True).first()
    if not tenant_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Profile not found")
    tenant_profile.is_active = False
    db.commit()
    db.refresh(tenant_profile)
    return tenant_profile


def create_tenant_profile_module(db: Session, tenant_profile_module_data: TenantProfileModuleCreate):
    tenant_profile_module_exists = (
        db.query(TenantProfileModule)
        .filter_by(
            tenant_profile_id=tenant_profile_module_data.tenant_profile_id,
            module_id=tenant_profile_module_data.module_id,
        )
        .first()
    )
    if tenant_profile_module_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant Profile Module already exists")
    if not db.query(
        exists().where(and_(tenant_profile_module_data.tenant_profile_id == TenantProfile.id, TenantProfile.is_active))
    ).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Profile not found")
    if not db.query(exists().where(and_(tenant_profile_module_data.module_id == Module.id, Module.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    tenant_profile_module = TenantProfileModule(
        tenant_profile_id=tenant_profile_module_data.tenant_profile_id, module_id=tenant_profile_module_data.module_id
    )
    db.add(tenant_profile_module)
    db.commit()
    return tenant_profile_module


def create_tenant_profile_modules_by_list(db: Session, data: TenantProfileModuleList):
    tenant_profile_modules = []
    for module_id in data.modules:
        exists = (
            db.query(TenantProfileModule)
            .filter_by(tenant_profile_id=data.tenant_profile_id, module_id=module_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant Profile Module already exists")
        if not db.query(TenantProfile).filter_by(id=data.tenant_profile_id, is_active=True).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant Profile not found")
        if not db.query(Module).filter_by(id=module_id, is_active=True).first():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
        new_tenant_profile_module = TenantProfileModule(tenant_profile_id=data.tenant_profile_id, module_id=module_id)
        db.add(new_tenant_profile_module)
        db.commit()
        tenant_profile_modules.append(new_tenant_profile_module)
    return tenant_profile_modules


def get_modules_by_tenant_profile_id(db: Session, tenant_profile_id: int):
    return db.query(TenantProfileModule).filter_by(tenant_profile_id=tenant_profile_id)
