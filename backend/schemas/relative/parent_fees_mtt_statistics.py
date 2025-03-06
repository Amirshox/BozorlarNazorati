from typing import Optional

from pydantic import BaseModel


class ParentFeesMttStatistics(BaseModel):
    mtt_id: Optional[int] = None
    mtt_name: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    mtt_phone: Optional[str] = None
    header_name: Optional[str] = None
    header_phone: Optional[str] = None
    workers_total: Optional[int] = None
    kids_total: Optional[int] = None
