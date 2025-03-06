from datetime import date
from typing import TypedDict

import requests
import sentry_sdk
from fastapi import HTTPException
from requests.exceptions import RequestException

from utils.log import timeit

FACE_AUTH_BASE_URL = "https://face-auth.istream.uz/"
FACE_AUTH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTg4OTgxMTQ2MX0.FZAgHzfIARxoqu8KvhE8ebMPDAibtac6bMwFYGiWs6w"  # noqa


class FaceAuthResponseType(TypedDict):
    is_authenticated: bool
    is_face_matched: bool
    distance: int
    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    is_spoofed: bool
    spoofing_score: int
    spoof_bucket_name: str
    spoof_object_name: str
    local_is_spoofed: bool
    local_spoofing_score: int
    bucket_name: str
    object_name: str
    has_permissions: bool
    signature: str


@timeit
def verify_face(pinfl: str, birth_date: date, photo: str) -> FaceAuthResponseType:
    url = f"{FACE_AUTH_BASE_URL}face_auth/insightface"
    headers = {"Authorization": f"Bearer {FACE_AUTH_TOKEN}"}

    data = {
        "external_id": "1",
        "external_user_id": "1",
        "individual_personal_number": pinfl,
        "given_date": birth_date.strftime("%Y-%m-%d"),
        "image_data": photo,
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()
    except RequestException as e:
        sentry_sdk.capture_exception(e)
        data = {
            "message": "Yuzni tekshirishda xatolik yuz berdi, iltimos keyinroq urinib ko'ring",
            "error": str(e),
        }
        raise HTTPException(status_code=200, detail=data) from e


@timeit
def verify_insight_face(pinfl: str, birth_date: date, photo: str) -> FaceAuthResponseType:
    url = f"{FACE_AUTH_BASE_URL}face_auth/insightface"
    headers = {"Authorization": f"Bearer {FACE_AUTH_TOKEN}"}

    data = {
        "external_user_id": "1",
        "individual_personal_number": pinfl,
        "given_date": birth_date.strftime("%Y-%m-%d"),
        "image_data": photo,
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()

    try:
        err_response = response.json()
        message = err_response["detail"]
    except Exception as e:
        print(e)
        message = response.text

    raise HTTPException(status_code=response.status_code, detail=message)


@timeit
def verify_insight_face_async(_id: int, pinfl: str, birth_date: date, image_url: str):
    url = f"{FACE_AUTH_BASE_URL}face_search/async/insightface"
    headers = {"Authorization": f"Bearer {FACE_AUTH_TOKEN}"}

    data = {
        "uuid": f"identity_photo.{_id}",
        "external_user_id": "1",
        "individual_personal_number": pinfl,
        "given_date": birth_date.strftime("%Y-%m-%d"),
        "image_url": image_url,
        "callback_endpoint": "https://api.realsoft.ai/tenant/identity/passport/verification/result",
        "on_failure_callback_endpoint": "https://api.realsoft.ai/tenant/identity/passport/verification/result",
    }

    response = requests.post(url, headers=headers, json=data)
    return response
