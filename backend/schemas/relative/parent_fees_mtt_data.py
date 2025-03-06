from typing import Optional

from pydantic import BaseModel


class ParentFeesMttDataSchema(BaseModel):
    kid_id: Optional[int] = None
    mtt_id: Optional[int] = None
    kid_name: Optional[str] = None
    birth_date: Optional[str] = None
    kid_photo: Optional[str] = None
    mtt_name: Optional[str] = None
    address: Optional[str] = None
    mtt_location: Optional[str] = None
    educators: Optional[str] = None
    educator_photos: Optional[str] = None
    header_name: Optional[str] = None
    header_phone: Optional[str] = None
    mtt_phone: Optional[str] = None
    header_photo: Optional[str] = None
    gender: Optional[int] = None
    visit_date: Optional[str] = None
    kassa_id: Optional[str] = None
    kid_pinfl: Optional[str] = None
    kid_metrics: Optional[str] = None
    group_name: Optional[str] = None
    gorup_worker_name: Optional[str] = None
    accepted_date: Optional[str] = None
    payment: Optional[int] = None
    last_payment: Optional[int] = None
    payment_date: Optional[str] = None
    region_id: Optional[int] = None
    district_id: Optional[int] = None
    region_name: Optional[str] = None
    district_name: Optional[str] = None
