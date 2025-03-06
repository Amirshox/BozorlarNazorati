from typing import Optional

from pydantic import BaseModel


class ParentFeesKidPay(BaseModel):
    kid_id: Optional[int] = None
    mtt_id: Optional[int] = None
    debt: Optional[int] = None
    paid: Optional[int] = None
    paid_date: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    card: Optional[str] = None
    kid_name: Optional[str] = None
    mtt_name: Optional[str] = None
    ofd_check: Optional[str] = None
    transaction_id: Optional[str] = None
