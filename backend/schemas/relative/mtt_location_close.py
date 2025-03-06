from typing import List, Optional
from pydantic import BaseModel, Field


class MttLocationCloseMtt(BaseModel):
    mtt_id: Optional[int] = None
    mtt_name: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    mfy: Optional[str] = None
    polygon: Optional[str] = None
    score: Optional[float] = None
    mtt_type: Optional[int] = None
    address: Optional[str] = None
    header_name: Optional[str] = None
    mobile_phone: Optional[str] = None
    phone: Optional[str] = None
    capacity: Optional[int] = None
    total_kids: Optional[int] = None
    free_place: Optional[int] = None


class MttLocationCloseGroup(BaseModel):
    id: Optional[int] = None
    name: Optional[str] = None
    total_kids: Optional[int] = None


class MttLocationCloseMttId(BaseModel):
    mtt: Optional[MttLocationCloseMtt]
    group: List[MttLocationCloseGroup] = Field(default_factory=list)


class MttLocationCloseDistance(BaseModel):
    mtt_id: Optional[int] = None
    score: Optional[float] = None
    mtt_name: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    mfy: Optional[str] = None
    mtt_type: Optional[int] = None
    polygon: Optional[str] = None
    address: Optional[str] = None
    header_name: Optional[str] = None
    mobile_phone: Optional[str] = None
    phone: Optional[str] = None
    capacity: Optional[int] = None
    total_kids: Optional[int] = None
    free_place: Optional[int] = None
    distance: Optional[float] = None


class RegionSchemas(BaseModel):
    id: int
    name: str


class MttPhotosSchema(BaseModel):
    photo: Optional[str] = None


class RelativeAttendanceReportData(BaseModel):
    kid_id: int
    mtt_id: int
    visit_date: str
    bucket_name: str | None = None
    object_name: str | None = None
