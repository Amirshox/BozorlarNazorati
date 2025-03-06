import os
import random
import tempfile
from datetime import date

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from auth.oauth2 import create_access_token, create_refresh_token
from config import NODAVLAT_BOGCHA_BASE_URL, NODAVLAT_BOGCHA_PASSWORD, NODAVLAT_BOGCHA_USERNAME
from database.hash import pwd_cxt
from models import Relative
from services.face_auth import verify_face
from services.relative.reset import send_new_password_vs_phone_to_platon
from services.wservice import get_info
from utils.image_processing import get_image_from_query, make_minio_url_from_image
from utils.kindergarten import get_user_photo_by_pinfl

RELATIVE_IDENTITY_BUCKET = os.getenv("MINIO_RELATIVE_IDENTITY", "relative-identity")


def generate_parent_username(passport: str) -> str:
    symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    gen = "".join(random.choices(symbols, k=4))
    return passport + "_" + gen


def generate_password() -> str:
    symbols = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(random.choices(symbols, k=8))


def relative_login_service(db: Session, username: str, password: str) -> dict:
    relative = db.query(Relative).filter_by(username=username).first()

    if relative is None:
        raise HTTPException(status_code=400, detail="Relative not found")

    if not pwd_cxt.verify(password, relative.password):
        raise HTTPException(status_code=400, detail="Incorrect password")

    access_token = create_access_token(data={"sub": username, "type": "relative", "scopes": ["relative"]})
    refresh_token = create_refresh_token(data={"username": username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": username,
        "user_type": "relative",
    }


def send_created_relative(relative: Relative) -> bool:
    photo_id = None
    if relative.photo:
        photo = relative.photo
        image_response = requests.get(photo)
        image_data = image_response.content

        with tempfile.NamedTemporaryFile(suffix=".jpeg") as temp_file:
            temp_file.write(image_data)
            temp_file.flush()
            temp_file.seek(0)  # Move to the beginning of the file

            files = {"file": ("image.jpeg", temp_file, "image/jpeg")}

            r_photo = requests.post(
                url="https://api.nodavlat-bogcha.uz/files/upload/category/parent_photos", files=files
            )
            try:
                photo_id = r_photo.json()["id"]
            except Exception as e:
                print(e)

    relative_data = {
        "id": relative.id,
        "passport_num": relative.passport_serial,
        "birthdate": relative.birth_date.strftime("%Y-%m-%d"),
        "pinfl": relative.pinfl,
        "tin": relative.tin,
        "surname": relative.patronymic_name,
        "firstname": relative.first_name,
        "lastname": relative.last_name,
        "gender": relative.gender,
        "phone": relative.phone,
        "full_name": relative.full_name,
        "passport_date": relative.passport_date_begin,
        "passport_department": relative.passport_given_place,
        "passport_term": relative.passport_date_end,
        "obl_id": relative.region_id,
        "area_id": relative.district_id,
        "photo": photo_id,
        "username": relative.username,
        "password": relative.pwd,
    }
    r = requests.post(
        url=f"{NODAVLAT_BOGCHA_BASE_URL}parent/register",
        auth=(NODAVLAT_BOGCHA_USERNAME, NODAVLAT_BOGCHA_PASSWORD),
        json=relative_data,
    )
    return r.status_code == 200


def relative_login_face_service(
    db: Session, minio_client, pinfl: str, birth_date: date, photo: str, phone: str
) -> dict:
    face_auth_response = verify_face(pinfl=pinfl, birth_date=birth_date, photo=photo)

    if face_auth_response["is_authenticated"]:
        relative = db.query(Relative).filter_by(pinfl=pinfl).first()
        has_pinfl_data = False
        has_photo = False
        if relative and relative.passport_serial:
            has_pinfl_data = True
        if relative and relative.photo:
            has_photo = True
        pinfl_data = get_info(pinfl=pinfl, birth_date=birth_date) if not has_pinfl_data else None
        main_photo_url = None
        if not has_photo:
            try:
                photo_result = get_user_photo_by_pinfl(pinfl=relative.pinfl)
                if photo_result["success"]:
                    main_image = get_image_from_query(photo_result["photo"])
                    main_photo_url = make_minio_url_from_image(
                        minio_client, main_image, RELATIVE_IDENTITY_BUCKET, relative.pinfl, is_check_hd=False
                    )
            except Exception as e:
                print(f"get_relative_photo: {e}")
        new_password = generate_password()
        is_new_relative = False
        if relative is None:
            relative = Relative(
                first_name=pinfl_data["first_name"],
                last_name=pinfl_data["last_name"],
                full_name=pinfl_data["full_name"],
                pinfl=pinfl,
                phone=phone,
                passport_serial=pinfl_data["passport_serial"],
                birth_date=date.fromisoformat(pinfl_data["birth_date"]),
                address=pinfl_data["address"],
                gender=pinfl_data["gender"],
                username=generate_parent_username(pinfl_data["passport_serial"]),
                password=pwd_cxt.hash(new_password),
                pwd=new_password,
                photo=main_photo_url,
                tin=pinfl_data["tin"],
                patronymic_name=pinfl_data["patronymic_name"],
                region_id=pinfl_data.get("region_id"),
                district_id=pinfl_data.get("district_id"),
                passport_given_place=pinfl_data.get("passport_given_place"),
                passport_date_begin=pinfl_data.get("passport_date_begin"),
                passport_date_end=pinfl_data.get("passport_date_end"),
            )
            db.add(relative)
            db.commit()
            db.refresh(relative)
            is_new_relative = True
        else:
            if main_photo_url:
                relative.photo = main_photo_url
            if pinfl_data:
                relative.first_name = pinfl_data["first_name"]
                relative.last_name = pinfl_data["last_name"]
                relative.full_name = pinfl_data["full_name"]
                relative.passport_serial = pinfl_data["passport_serial"]
                relative.birth_date = pinfl_data["birth_date"]
                relative.address = pinfl_data["address"]
                relative.gender = pinfl_data["gender"]
                relative.username = generate_parent_username(pinfl_data["passport_serial"])
                relative.password = pwd_cxt.hash(new_password)
                relative.pwd = new_password
                relative.phone = phone
                relative.tin = pinfl_data["tin"]
                relative.patronymic_name = pinfl_data["patronymic_name"]
                relative.region_id = pinfl_data["region_id"]
                relative.district_id = pinfl_data["district_id"]
                relative.passport_given_place = pinfl_data["passport_given_place"]
                relative.passport_date_begin = pinfl_data["passport_date_begin"]
                relative.passport_date_end = pinfl_data["passport_date_end"]
                is_new_relative = True
            phone_changed = False
            if phone != relative.phone:
                phone_changed = True
                relative.phone = phone
            if main_photo_url or pinfl_data or phone_changed:
                db.commit()
                db.refresh(relative)
                if phone_changed:
                    is_sent = send_new_password_vs_phone_to_platon(relative)
                    print("New phone sent to Nodavlat Bogcha:", is_sent)

        if is_new_relative:
            is_sent = send_created_relative(relative)
            print("Created relative sent to Nodavlat Bogcha:", is_sent)

        access_token = create_access_token(data={"sub": relative.username, "type": "relative", "scopes": ["relative"]})
        refresh_token = create_refresh_token(data={"username": relative.username})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "username": relative.username,
            "user_type": "relative",
        }

    raise HTTPException(status_code=400, detail="Face not matched")
