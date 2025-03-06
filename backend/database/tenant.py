from typing import List

from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import District, Tenant, TenantProfile
from schemas.tenant import TenantCreate, TenantUpdate


def get_tenants(db: Session, is_active: bool = True):
    return db.query(Tenant).filter_by(is_active=is_active)


def get_3rd_tenants(db: Session, ids: List[int]):
    return db.query(Tenant).filter(Tenant.id.in_(ids), Tenant.is_active)


def get_tenant(db: Session, pk: int, is_active: bool = True):
    tenant = db.query(Tenant).filter_by(id=pk, is_active=is_active).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def create_tenant(db: Session, tenant: TenantCreate):
    tenant_exists = db.query(Tenant).filter_by(name=tenant.name).first()
    if tenant_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant already exists")

    tenant_profile = db.query(TenantProfile).filter_by(id=tenant.tenant_profile_id, is_active=True).first()
    if not tenant_profile:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant profile not found")

    tenant = Tenant(
        name=tenant.name,
        description=tenant.description,
        logo=tenant.logo,
        district_id=tenant.district_id,
        country_id=tenant.country_id,
        region_id=tenant.region_id,
        zip_code=tenant.zip_code,
        phone=tenant.phone,
        email=tenant.email,
        website=tenant.website,
        tenant_profile_id=tenant.tenant_profile_id,
    )
    db.add(tenant)
    db.commit()
    return tenant


def update_tenant(db: Session, pk: int, tenant: TenantUpdate):
    tenant_exists = db.query(Tenant).filter_by(name=tenant.name).first()
    if tenant_exists and tenant_exists.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"You can not update tenant name with `{tenant.name}`"
        )
    db_tenant = db.query(Tenant).filter_by(id=pk).first()
    if not db_tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if not db.query(exists().where(and_(tenant.district_id == District.id, District.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")

    if not db.query(
        exists().where(and_(tenant.tenant_profile_id == TenantProfile.id, TenantProfile.is_active))
    ).scalar():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant profile not found")

    if tenant.name:
        db_tenant.name = tenant.name
    if tenant.description:
        db_tenant.description = tenant.description
    if tenant.logo:
        db_tenant.logo = tenant.logo
    if tenant.district_id:
        db_tenant.district_id = tenant.district_id
    if tenant.country_id:
        db_tenant.country_id = tenant.country_id
    if tenant.region_id:
        db_tenant.region_id = tenant.region_id
    if tenant.zip_code:
        db_tenant.zip_code = tenant.zip_code
    if tenant.phone:
        db_tenant.phone = tenant.phone
    if tenant.email:
        db_tenant.email = tenant.email
    if tenant.website:
        db_tenant.website = tenant.website
    if tenant.tenant_profile_id:
        db_tenant.tenant_profile_id = tenant.tenant_profile_id
    db.commit()
    db.refresh(db_tenant)

    return db_tenant


def delete_tenant(db: Session, pk: int):
    tenant = db.query(Tenant).filter_by(id=pk, is_active=True).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.is_active = False
    db.commit()
    return tenant
