from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SmartCameraTaskBase(BaseModel):
    task_type: str
    smart_camera_id: int
    is_sent: bool = False


class SmartCameraTaskResultBase(BaseModel):
    task_id: int
    status_code: int
    success_count: Optional[int] = 0
    error_count: Optional[int] = 0


class SmartCameraTaskResultInDB(SmartCameraTaskResultBase):
    id: int
    created_at: datetime
    updated_at: datetime


class SmartCameraTaskUserBase(BaseModel):
    task_id: int
    visitor_id: Optional[int] = None
    identity_id: Optional[int] = None
    wanted_id: Optional[int] = None
    relative_id: Optional[int] = None


class SmartCameraTaskInDB(SmartCameraTaskBase):
    id: int
    users: Optional[List[SmartCameraTaskUserBase]] = None
    created_at: datetime
    updated_at: datetime
