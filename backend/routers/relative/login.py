from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_pg_db
from database.minio_client import get_minio_client
from services.relative.login import relative_login_face_service, relative_login_service

router = APIRouter(prefix="/login", tags=["login"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    user_type: str


@router.post("", response_model=LoginResponse)
def relative_login(request_data: LoginRequest, db: Session = Depends(get_pg_db)):
    data = relative_login_service(db, username=request_data.username, password=request_data.password)
    return data


class LoginFaceRequest(BaseModel):
    pinfl: str
    birth_date: date
    photo: str
    phone: str


class LoginFaceResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    user_type: str


@router.post("/face", response_model=LoginFaceResponse)
def relative_face_login(
    request_data: LoginFaceRequest, db: Session = Depends(get_pg_db), minio_client=Depends(get_minio_client)
):
    def is_valid_phone(phone: str) -> bool:
        return len(phone) == 12 and phone.isdigit()

    if not is_valid_phone(request_data.phone):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")
    response = relative_login_face_service(
        db, minio_client, request_data.pinfl, request_data.birth_date, request_data.photo, request_data.phone
    )
    return response
