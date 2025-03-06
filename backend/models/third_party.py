from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from models.base import BaseModel


class ThirdPartyIntegration(BaseModel):
    __tablename__ = "third_party_integration"
    name = Column(String)
    email = Column(String)
    phone = Column(String)
    api = Column(String)
    username = Column(String)
    password = Column(String)
    auth_type = Column(String)  # basic or jwt or None
    api_username = Column(String)
    api_password = Column(String)
    api_token = Column(String)
    api_token_type = Column(String)  # default=bearer

    tenants = relationship("ThirdPartyIntegrationTenant", back_populates="integration")


class ThirdPartyIntegrationTenant(BaseModel):
    __tablename__ = "third_party_integration_tenant"
    third_party_integration_id = Column(Integer, ForeignKey("third_party_integration.id"))
    tenant_id = Column(Integer, ForeignKey("tenant.id"))

    integration = relationship("ThirdPartyIntegration", back_populates="tenants")


class AllowedEntity(BaseModel):
    __tablename__ = "allowed_entity"
    tenant_id = Column(Integer)
    tenant_entity_id = Column(Integer)
