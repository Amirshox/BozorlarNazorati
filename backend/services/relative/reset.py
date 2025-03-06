import requests
from sqlalchemy.orm import Session

from auth.oauth2 import create_access_token, create_refresh_token
from config import NODAVLAT_BOGCHA_BASE_URL, NODAVLAT_BOGCHA_PASSWORD, NODAVLAT_BOGCHA_USERNAME
from database.hash import pwd_cxt
from models import Relative


def send_new_password_vs_phone_to_platon(relative) -> bool:
    r = requests.put(
        url=f"{NODAVLAT_BOGCHA_BASE_URL}parent/auth",
        auth=(NODAVLAT_BOGCHA_USERNAME, NODAVLAT_BOGCHA_PASSWORD),
        json={
            "pinfl": relative.pinfl,
            "username": relative.username,
            "password": relative.pwd,
            "phone": relative.phone,
        },
    )
    return r.status_code == 200


def relative_reset_service(db: Session, relative: Relative, new_password: str):
    is_new_password = False
    if new_password != relative.pwd:
        is_new_password = True
    relative.password = pwd_cxt.hash(new_password)
    relative.pwd = new_password
    db.commit()
    db.refresh(relative)
    if is_new_password:
        is_sent = send_new_password_vs_phone_to_platon(relative)
        print("New Password sent to Nodavlat Bogcha:", is_sent)

    access_token = create_access_token(data={"sub": relative.username, "type": "relative", "scopes": ["relative"]})
    refresh_token = create_refresh_token(data={"username": relative.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": relative.username,
        "user_type": "relative",
    }
