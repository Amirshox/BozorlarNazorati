from typing import Optional

from pydantic import BaseModel


class ParentFeesKidVisitData(BaseModel):
    visit_date: Optional[str] = None
    verified_at: Optional[str] = None
    visit_photo: Optional[str] = None
    kid_name: Optional[str] = None
    bucket: Optional[str] = None
    object_name: Optional[str] = None
