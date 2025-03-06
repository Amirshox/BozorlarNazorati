from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import Module, Tenant
from models.integration import Integrations
from schemas.integration import IntegrationsBase, IntegrationsUpdate


def create_integration(db: Session, tenant_id: int, data: IntegrationsBase):
    tenant = db.query(Tenant).filter_by(id=tenant_id, is_active=True).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")
    module = db.query(Module).filter_by(id=data.module_id, is_active=True).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found or inactive")

    if not db.query(exists().where(and_(Tenant.id == tenant.id, Tenant.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant does not exist")

    if not db.query(exists().where(and_(Module.id == data.module_id, Module.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Module does not exist")

    new_integration = Integrations(
        tenant_id=tenant_id,
        module_id=data.module_id,
        callback_url=data.callback_url,
        identity_callback_url=data.identity_callback_url,
        auth_type=data.auth_type,
        username=data.username,
        password=data.password,
        token=data.token,
        token_type=data.token_type,
    )
    db.add(new_integration)
    db.commit()
    db.refresh(new_integration)

    return new_integration


def get_integration(db: Session, pk: int, tenant_id: int, is_active: bool = True):
    integration = db.query(Integrations).filter_by(tenant_id=tenant_id, id=pk, is_active=is_active).first()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found or inactive")
    return integration


def get_integrations(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(Integrations).filter_by(tenant_id=tenant_id, is_active=is_active)


def update_integration(db: Session, pk: int, tenant_id: int, data: IntegrationsUpdate):
    module = db.query(Module).filter_by(id=data.module_id, is_active=True).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found or inactive")
    integration = db.query(Integrations).filter_by(tenant_id=tenant_id, id=pk).first()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    if data.module_id:
        integration.module_id = data.module_id
    if data.callback_url:
        integration.callback_url = data.callback_url
    if data.identity_callback_url:
        integration.identity_callback_url = data.identity_callback_url
    if data.auth_type:
        integration.auth_type = data.auth_type
    if data.username:
        integration.username = data.username
    if data.password:
        integration.password = data.password
    if data.token:
        integration.token = data.token
    if data.token_type:
        integration.token_type = data.token_type
    db.commit()
    db.refresh(integration)
    return integration


def delete_integration(db: Session, pk: int, tenant_id: int):
    integration = db.query(Integrations).filter_by(tenant_id=tenant_id, id=pk, is_active=True).first()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found or inactive")
    integration.is_active = False
    db.commit()
    return integration
