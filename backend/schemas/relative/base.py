from datetime import date
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel

from schemas.identity import IdentityInDBForRelative


class BaseResponseSchema(BaseModel):
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: Optional[str] = None
    status: Optional[int] = None
    path: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    response: Optional[Dict[str, Any]] = None


T = TypeVar("T")


class GenericResponseSchema(BaseResponseSchema, Generic[T]):
    data: Optional[List[T]] = None


class RelativeMeSchema(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: Optional[str] = None
    pinfl: Optional[str] = None
    passport_serial: Optional[str] = None
    birth_date: Optional[date] = None
    username: Optional[str] = None
    email: Optional[str] = None
    photo: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[int] = None


class UserSetPasswordResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    user_type: str


class RelativeChildrenData(BaseModel):
    kid_id: int
    mtt_id: int
    kid_name: str | None = None
    birth_date: str | None = None
    kid_photo: str | None = None
    mtt_name: str | None = None
    address: str | None = None
    mtt_location: str | None = None
    educators: str | None = None
    educator_photos: str | None = None
    header_name: str | None = None
    header_phone: str | None = None
    mtt_phone: str | None = None
    header_photo: str | None = None
    gender: int | None = None
    visit_date: str | None = None
    kassa_id: str | None = None
    kid_pinfl: str | None = None
    kid_metrics: str | None = None
    group_name: str | None = None
    gorup_worker_name: str | None = None
    accepted_date: str | None = None
    payment: int | None = None
    last_payment: int | None = None
    payment_date: str | None = None
    region_id: int | None = None
    district_id: int | None = None
    region_name: str | None = None
    district_name: str | None = None


class RelativeChildrenResponse(BaseModel):
    from_api: List[RelativeChildrenData] | None = None
    from_db: List[IdentityInDBForRelative] | None = None


class NotificationNotFoundKassa_idData(BaseModel):
    kid_id: int
    mtt_id: int
    image: str | None = None
    external_link: str | None = None
