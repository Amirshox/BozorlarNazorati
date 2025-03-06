from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WantedBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    photo: str
    phone: Optional[str] = None
    pinfl: Optional[str] = None
    concern_level: int = 1
    accusation: Optional[str] = None
    description: Optional[str] = None
    tenant_entity_id: Optional[int] = None


class WantedUpdate(WantedBase):
    tenant_id: Optional[int] = None


class WantedInDB(WantedBase):
    id: int
    created_at: datetime
    updated_at: datetime
