from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import AllowedEntity, Tenant, TenantEntity, ThirdPartyIntegration, ThirdPartyIntegrationTenant
from schemas.third_party import AllowedEntityCreate, ThirdPartyIntegrationCreate, ThirdPartyIntegrationUpdate
from utils.generator import no_bcrypt


def create_third_party(db: Session, data: ThirdPartyIntegrationCreate):
    same_exist = db.query(ThirdPartyIntegration).filter_by(name=data.name, is_active=True).first()
    if same_exist:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="ThirdPartyIntegration with same name already exists"
        )
    exist_username = db.query(ThirdPartyIntegration).filter_by(username=data.username).first()
    if exist_username:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    third_party = ThirdPartyIntegration(
        name=data.name,
        email=data.email,
        phone=data.phone,
        api=data.api,
        username=data.username,
        auth_type=data.auth_type,
        password=no_bcrypt(data.password),
        api_username=data.api_username,
        api_password=data.api_password,
        api_token=data.api_token,
        api_token_type=data.api_token_type,
    )
    db.add(third_party)
    db.commit()
    db.refresh(third_party)
    for tenant_id in data.tenant_ids:
        tenant = db.query(Tenant).filter_by(id=tenant_id, is_active=True).first()
        if tenant:
            exists_one = (
                db.query(ThirdPartyIntegrationTenant)
                .filter_by(third_party_integration_id=third_party.id, tenant_id=tenant.id, is_active=True)
                .first()
            )
            if not exists_one:
                third_party_tenant = ThirdPartyIntegrationTenant(
                    third_party_integration_id=third_party.id, tenant_id=tenant_id
                )
                db.add(third_party_tenant)
                db.commit()
                db.refresh(third_party_tenant)
    return third_party


def get_third_party_by_username(db: Session, username: str):
    return db.query(ThirdPartyIntegration).filter_by(username=username).first()


def get_third_party_integrations(db: Session, is_active: bool = True):
    return db.query(ThirdPartyIntegration).filter_by(is_active=is_active)


def get_third_party(db: Session, pk: int, is_active: bool = True):
    third_party = db.query(ThirdPartyIntegration).filter_by(id=pk, is_active=is_active).first()
    if not third_party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ThirdParty does not exist")
    return third_party


def update_3rd_party_only_tenants(db: Session, pk: int, tenant_ids: List[int]):
    third_party = db.query(ThirdPartyIntegration).filter_by(id=pk, is_active=True).first()
    if not third_party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ThirdPartyIntegration does not exist")
    for third_party_tenant in third_party.tenants:
        if third_party_tenant.is_active and third_party_tenant.tenant_id not in tenant_ids:
            third_party_tenant.is_active = False
            db.commit()
            db.refresh(third_party_tenant)
    third_party_tenants = (
        db.query(ThirdPartyIntegrationTenant).filter_by(third_party_integration_id=pk, is_active=True).all()
    )
    db_ids = [item.tenant_id for item in third_party_tenants]
    for tenant_id in tenant_ids:
        if tenant_id not in db_ids:
            third_party_tenant = ThirdPartyIntegrationTenant(third_party_integration_id=pk, tenant_id=tenant_id)
            db.add(third_party_tenant)
            db.commit()
            db.refresh(third_party_tenant)
    third_party = db.query(ThirdPartyIntegration).filter_by(id=pk, is_active=True).first()
    return third_party


def update_third_party(db: Session, pk: int, data: ThirdPartyIntegrationUpdate):
    same_exists = db.query(ThirdPartyIntegration).filter_by(name=data.name, is_active=True).first()
    if same_exists and same_exists.id != pk:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="ThirdPartyIntegration already exists")
    third_party = db.query(ThirdPartyIntegration).filter_by(id=pk, is_active=True).first()
    if not third_party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ThirdPartyIntegration does not exist")
    if data.name:
        third_party.name = data.name
    if data.email:
        third_party.email = data.email
    if data.phone:
        third_party.phone = data.phone
    if data.api:
        third_party.api = data.api
    if data.auth_type:
        third_party.auth_type = data.auth_type
    if data.api_username:
        third_party.api_username = data.api_username
    if data.api_password:
        third_party.api_password = data.api_password
    if data.api_token:
        third_party.api_token = data.api_token
    if data.api_token_type:
        third_party.api_token_type = data.api_token_type
    db.commit()
    db.refresh(third_party)
    for third_party_tenant in third_party.tenants:
        if third_party_tenant.is_active and third_party_tenant.tenant_id not in data.tenant_ids:
            third_party_tenant.is_active = False
            db.commit()
            db.refresh(third_party_tenant)
    third_party_tenants = (
        db.query(ThirdPartyIntegrationTenant).filter_by(third_party_integration_id=pk, is_active=True).all()
    )
    db_ids = [item.tenant_id for item in third_party_tenants]
    for tenant_id in data.tenant_ids:
        if tenant_id not in db_ids:
            third_party_tenant = ThirdPartyIntegrationTenant(third_party_integration_id=pk, tenant_id=tenant_id)
            db.add(third_party_tenant)
            db.commit()
            db.refresh(third_party_tenant)
    third_party = db.query(ThirdPartyIntegration).filter_by(id=pk, is_active=True).first()
    return third_party


def delete_third_party(db: Session, pk: int):
    third_party = db.query(ThirdPartyIntegration).filter_by(id=pk, is_active=True).first()
    if not third_party:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ThirdPartyIntegration does not exist")
    third_party.is_active = False
    db.commit()
    db.refresh(third_party)
    third_party_tenants = (
        db.query(ThirdPartyIntegrationTenant).filter_by(third_party_integration_id=pk, is_active=True).all()
    )
    for third_party_tenant in third_party_tenants:
        third_party_tenant.is_active = False
        db.commit()
        db.refresh(third_party_tenant)
    return third_party


def create_allowed_entity(db: Session, data: AllowedEntityCreate):
    exist_allowed_entity = (
        db.query(AllowedEntity).filter_by(tenant_id=data.tenant_id, tenant_entity_id=data.tenant_entity_id).first()
    )

    if exist_allowed_entity:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entity already exists")

    entity = (
        db.query(TenantEntity).filter_by(id=data.tenant_entity_id, tenant_id=data.tenant_id, is_active=True).first()
    )
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")

    new_allowed_entity = AllowedEntity(tenant_id=data.tenant_id, tenant_entity_id=data.tenant_entity_id)
    db.add(new_allowed_entity)
    db.commit()
    db.refresh(new_allowed_entity)
    return new_allowed_entity


def delete_allowed_entity(db: Session, pk: int):
    allowed_entity = db.query(AllowedEntity).filter_by(id=pk).first()
    if allowed_entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowed entity not found")
    db.delete(allowed_entity)
    db.commit()
    return {"message": "Allowed entity deleted successfully"}
