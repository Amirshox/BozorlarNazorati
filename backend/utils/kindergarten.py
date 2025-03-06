import os

import requests

from utils.log import timeit

NODAVLAT_BASE_URL = os.getenv("NODAVLAT_BASE_URL")
WSERVICE_BASE_URL = "https://wservice.uz/gcp/"

BASIC_AUTH = {"Authorization": "Basic cmVhbHNvZnRhaTpyZWFsc29mdGFpNDU2NSE="}


def correct_lang(lang: str) -> str:
    return lang if lang in ["la", "uz", "ru"] else "la"


def get_birth_date_from_pinfl(pinfl: str) -> str:
    if pinfl[0] in ["3", "4"]:
        return f"19{pinfl[5:7]}-{pinfl[3:5]}-{pinfl[1:3]}"
    elif pinfl[0] in ["5", "6"]:
        return f"20{pinfl[5:7]}-{pinfl[3:5]}-{pinfl[1:3]}"
    else:
        return "1111-11-11"


@timeit
def get_auth_user(username: str, password: str, user_agent: str = None) -> dict:
    try:
        if user_agent:
            r = requests.post(
                url=f"{NODAVLAT_BASE_URL}auth/login",
                headers={"User-Agent": user_agent},
                json={"username": username, "password": password},
            )
        else:
            r = requests.post(url=f"{NODAVLAT_BASE_URL}auth/login", json={"username": username, "password": password})
    except Exception as e:
        print(f"get_auth_user error: {e}")
        return {"success": False, "data": None, "code": 400, "error": "Tashqi manba bilan bog'lanishda xatolik"}
    if r.status_code == 200:
        try:
            response = r.json()["user"]
            data = {
                "id": response["id"],
                "firstname": response["firstname"] if response["firstname"] else response["fullName"].split(" ")[1],
                "lastname": response["surname"] if response["surname"] else response["fullName"].split(" ")[0],
                "pinfl": response["pinfl"],
                "phone": response["mobilePhone"],
                "mtt_id": response["orgId"],
                "district_id": response["areaId"],
            }
        except Exception as e:
            return {"success": False, "data": None, "code": r.status_code, "error": str(e)}
        return {"success": True, "token": r.json()["token"], "data": data, "code": r.status_code, "error": None}
    return {"success": False, "data": None, "code": r.status_code, "error": r.text}


@timeit
def get_user_photo_by_pinfl(pinfl: str) -> dict:
    birth_date = get_birth_date_from_pinfl(pinfl)
    url = f"{WSERVICE_BASE_URL}v1/passport/photo?pinfl={pinfl}&birth_date={birth_date}"
    r = requests.get(url, auth=("one_system", "Y16!-}T'3M')90K6$Pk@"))
    if r.status_code == 200:
        response = r.json()["data"]
        return {"success": True, "photo": response["photo"], "code": 200, "error": None}
    return {"success": False, "photo": None, "code": r.status_code, "error": r.text}
