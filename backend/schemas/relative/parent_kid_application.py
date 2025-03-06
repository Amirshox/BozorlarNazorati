from typing import Optional

from pydantic import BaseModel


class ParentSdkAuthResponse(BaseModel):
    access_token: str
    access_token_issued_at: str
    refresh_token: str
    refresh_token_issued_at: str
    user_type: str


class ParentKidApplicationInDB(BaseModel):
    application_id: Optional[int] = None
    kid_name: Optional[str] = None
    relationship: Optional[str] = None
    created_date: Optional[str] = None
    status: Optional[str] = None
    check_person: Optional[str] = None
    check_time: Optional[str] = None
    reason: Optional[str] = None
    image: Optional[str] = None


class ParentKidApplicationStatus(BaseModel):
    application_id: Optional[int] = None
    kid_name: Optional[str] = None
    kid_photo: Optional[str] = None
    parent_pinfl: Optional[str] = None
    parent_photo: Optional[str] = None
    parent_name: Optional[str] = None
    parent_birth_date: Optional[str] = None
    relationship: Optional[str] = None
    status: Optional[str] = None


class RealPaySchema(BaseModel):
    result: str
