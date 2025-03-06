from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ThirdPartyIntegrationBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    api: str
    username: str
    password: str
    auth_type: Optional[str] = None
    api_username: Optional[str] = None
    api_password: Optional[str] = None
    api_token: Optional[str] = None
    api_token_type: Optional[str] = None


class ThirdPartyIntegrationTenantBase(BaseModel):
    third_party_integration_id: int
    tenant_id: int


class ThirdPartyIntegrationTenantInDB(ThirdPartyIntegrationTenantBase):
    id: int
    created_at: datetime
    updated_at: datetime


class ThirdPartyIntegrationCreate(ThirdPartyIntegrationBase):
    tenant_ids: List[int]


class ThirdPartyIntegrationUpdate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    api: str
    auth_type: Optional[str] = None
    api_username: Optional[str] = None
    api_password: Optional[str] = None
    api_token: Optional[str] = None
    api_token_type: Optional[str] = None
    tenant_ids: List[int]


class ThirdPartyIntegrationInDB(ThirdPartyIntegrationBase):
    id: int
    tenants: Optional[List[ThirdPartyIntegrationTenantBase]] = None
    created_at: datetime
    updated_at: datetime


class AllowedEntityResponse(BaseModel):
    id: int
    tenant_id: int
    tenant_entity_id: int
    created_at: datetime


class AllowedEntityCreate(BaseModel):
    tenant_id: int
    tenant_entity_id: int
