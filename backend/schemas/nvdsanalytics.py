import datetime
from datetime import time
from typing import List, Literal, Optional

from pydantic import BaseModel

from .infrastructure import CameraInDB, SmartCameraInDB
from .user import UserInDBBase


class RoiBase(BaseModel):
    name: str
    description: Optional[str] = None
    identity_id: Optional[int] = None
    labels: Optional[List[Literal["work-analytics", "safe-zone", "overcrowd-detection"]]] = None
    workspace_type: Optional[Literal["worker", "client"]] = None
    people_count_threshold: Optional[int] = None
    safe_zone_start_time: Optional[time] = None
    safe_zone_end_time: Optional[time] = None
    detection_object_type: Optional[Literal["person", "car"]] = None
    color: Optional[str] = None
    camera_id: Optional[int] = None
    smart_camera_id: Optional[int] = None


class PointBase(BaseModel):
    x: int
    y: int
    order_number: int
    roi_id: int


class PointCreate(BaseModel):
    x: int
    y: int
    order_number: int


class PointUpdate(PointCreate):
    id: int


class PointInDB(PointBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RoiLableInDB(BaseModel):
    id: int
    roi_id: int
    label_title: Literal["work-analytics", "safe-zone", "overcrowd-detection", "car-parking"]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RoiInDB(RoiBase):
    id: int
    points: Optional[List[PointInDB]] = None
    people_count_threshold: Optional[int] = None
    labels: Optional[List[RoiLableInDB]] = None
    safe_zone_start_time: Optional[time] = None
    safe_zone_end_time: Optional[time] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class BazaarRoi(BaseModel):
    name: str
    description: Optional[str] = None
    camera_id: Optional[int] = None
    smart_camera_id: Optional[int] = None
    color: Optional[str] = None
    shop_id: Optional[int] = None
    spot_id: Optional[int] = None
    points: List[PointCreate]


class BazaarRoiInDB(BazaarRoi):
    id: int


class CreateRoiRequest(RoiBase):
    points: List[PointCreate]


class BaazarRoiBulk(BaseModel):
    name: str
    color: Optional[str] = None
    shop_id: Optional[int] = None
    spot_id: Optional[int] = None
    points: List[PointCreate]


class CreateBazaarRoiInBulkRequest(BaseModel):
    smart_camera_id: int
    rois: List[BaazarRoiBulk]


class RoiPointUpdate(RoiBase):
    points: List[PointUpdate]


class InferenceDetectedObject(BaseModel):
    object_name: str
    conf_score: float


class InferenceResult(BaseModel):
    roi_id: Optional[int] = None
    shop_id: Optional[int] = None
    is_covered: Optional[bool] = None
    coverage_score: Optional[float] = None
    detected_objects: List[InferenceDetectedObject]


class RoiAnalyticsResponse(BaseModel):
    inference_result: Optional[List[InferenceResult]] = None
    inference_image: Optional[str] = None
    smart_camera_id: Optional[int] = None


class RoiAnalyticsHistory(RoiAnalyticsResponse):
    inference_date: str


class LineBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: str
    camera_id: Optional[int] = None
    smart_camera_id: Optional[int] = None
    dx1: int
    dy1: int
    dx2: int
    dy2: int
    x1: int
    y1: int
    x2: int
    y2: int


class LineUpdate(BaseModel):
    name: Optional[str]
    description: Optional[str] = None
    type: Optional[str]
    camera_id: Optional[int] = None
    smart_camera_id: Optional[int] = None
    dx1: Optional[int] = None
    dy1: Optional[int] = None
    dx2: Optional[int] = None
    dy2: Optional[int] = None
    x1: Optional[int] = None
    y1: Optional[int] = None
    x2: Optional[int] = None
    y2: Optional[int] = None


class LineInDB(LineBase):
    id: int
    camera: Optional[CameraInDB] = None
    smart_camera: Optional[SmartCameraInDB] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ScheduleTemplateBase(BaseModel):
    name: str
    description: Optional[str] = None
    tenant_id: int


class ScheduleBase(BaseModel):
    template_id: int
    weekday: int
    start_time: datetime.time
    end_time: datetime.time


class ScheduleCreate(BaseModel):
    weekday: int
    start_time: datetime.time
    end_time: datetime.time


class ScheduleUpdate(BaseModel):
    id: int
    weekday: int
    start_time: datetime.time
    end_time: datetime.time


class UserScheduleTemplateBase(BaseModel):
    user_id: int
    template_id: int


class ScheduleInDB(ScheduleBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ScheduleTemplateInDB(ScheduleTemplateBase):
    id: int
    schedules: Optional[List[ScheduleInDB]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ScheduleTemplateCreate(ScheduleTemplateBase):
    schedules: List[ScheduleCreate]


class ScheduleTemplateUpdate(ScheduleTemplateBase):
    schedules: List[ScheduleUpdate]


class UserScheduleTemplateInDB(UserScheduleTemplateBase):
    id: int
    user: Optional[UserInDBBase] = None
    template: Optional[ScheduleTemplateInDB] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ErrorSmartCameraBase(BaseModel):
    identity_id: Optional[int] = None
    user_id: Optional[int] = None
    smart_camera_id: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[int] = None
    is_sent: Optional[bool] = False
    is_resolved: Optional[bool] = False


class ErrorSmartCameraInDB(ErrorSmartCameraBase):
    id: int
    version: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RawRoiAnalytics(BaseModel):
    report_id: str
    jetson_device_id: str
    number_of_people: int
    roi_id: int
    timestamp: str
    frame_image: Optional[str] = None
    illegal_parking: bool
