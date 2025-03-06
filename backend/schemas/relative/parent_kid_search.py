from typing import Optional

from pydantic import BaseModel


class ParentKidSearch(BaseModel):
    kid_id: Optional[int] = None
    full_name: Optional[str] = None
    mtt_name: Optional[str] = None
    mtt_id: Optional[int] = None
    mtt_address: Optional[str] = None
    pinfl_metrics: Optional[str] = None
    kassa_id: Optional[str] = None
