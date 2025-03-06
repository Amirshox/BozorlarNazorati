from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VisitorBase(BaseModel):
    photo: str
    smart_camera_id: int
    tenant_entity_id: Optional[int] = None


class VisitorInDB(VisitorBase):
    id: int
    created_at: datetime
    updated_at: datetime


class VisitorAttendanceBase(BaseModel):
    smart_camera_id: int
    attendance_type: str
    attendance_datetime: datetime
    snapshot_url: str
    background_image_url: Optional[str] = None
    body_image_url: Optional[str] = None
    visitor_id: Optional[int] = None


class VisitorAttendanceInDB(VisitorAttendanceBase):
    id: int
    created_at: datetime
    updated_at: datetime
