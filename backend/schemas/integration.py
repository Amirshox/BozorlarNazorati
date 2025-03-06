from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IntegrationsBase(BaseModel):
    module_id: int
    callback_url: str
    identity_callback_url: Optional[str] = None
    auth_type: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    token_type: Optional[str] = None


class IntegrationsUpdate(IntegrationsBase):
    pass


class IntegrationsInDB(IntegrationsBase):
    id: int
    created_at: datetime
    updated_at: datetime
