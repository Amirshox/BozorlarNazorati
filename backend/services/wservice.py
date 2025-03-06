from datetime import date
from typing import TypedDict

import requests
from fastapi import HTTPException

from utils.log import timeit

WSERVICE_BASE_URL = "https://wservice.uz/"
WSERVICE_USERNAME = "online-bozor"
WSERVICE_PASSWORD = "GYwMjrwJVpSx"


class WServiceInfoResponseType(TypedDict):
    first_name: str
    last_name: str
    full_name: str
    pinfl: str
    passport_serial: str
    birth_date: str
    address: str
    gender: int
    tin: int
    patronymic_name: str
    region_id: int
    district_id: int
    passport_given_place: str
    passport_date_begin: str
    passport_date_end: str


@timeit
def get_info(pinfl: str, birth_date: date) -> WServiceInfoResponseType:
    url = f"{WSERVICE_BASE_URL}gcp/passport/info2/"

    params = {"pinfl": pinfl, "birth_date": birth_date}

    response = requests.get(url, auth=(WSERVICE_USERNAME, WSERVICE_PASSWORD), params=params, timeout=10)

    data = response.json()["data"]

    if response.status_code == 200 and data:
        return {
            "first_name": data["name"],
            "last_name": data["sur_name"],
            "full_name": data["full_name"],
            "pinfl": data["current_pinfl"],
            "passport_serial": data["current_document"],
            "birth_date": data["birth_date"],
            "address": data["address"],
            "gender": data["gender"],
            "tin": data["tin"],
            "patronymic_name": data["patronymic_name"],
            "region_id": data.get("region_id"),
            "district_id": data.get("district_id"),
            "passport_given_place": data.get("given_place"),
            "passport_date_begin": data.get("date_begin"),
            "passport_date_end": data.get("date_end"),
        }
    raise HTTPException(status_code=response.status_code, detail="Tashqi manbada xatolik!")


class WServiceParentInfoResponse(TypedDict):
    first_name: str
    last_name: str
    birth_date: str
    gender: int
    father_pinfl: str
    father_first_name: str
    father_last_name: str
    father_birth_date: str
    mother_pinfl: str
    mother_first_name: str
    mother_last_name: str
    mother_birth_date: str


@timeit
def get_parent_info(pinfl: str) -> WServiceParentInfoResponse:
    url = f"{WSERVICE_BASE_URL}fhdyo/v1/act/birth?pinfl={pinfl}"
    response = requests.get(url, auth=(WSERVICE_USERNAME, WSERVICE_PASSWORD), timeout=10)
    data = response.json()["data"]
    if response.status_code == 200 and data:
        return {
            "first_name": data["name"],
            "last_name": data["surname"],
            "birth_date": data["birth_date"],
            "gender": data["gender_code"],
            "father_pinfl": str(data["father_pinfl"]),
            "father_first_name": data["father_name"],
            "father_last_name": data["father_surname"],
            "father_birth_date": data["father_birth_date"],
            "mother_pinfl": str(data["mother_pinfl"]),
            "mother_first_name": data["mother_name"],
            "mother_last_name": data["mother_surname"],
            "mother_birth_date": data["mother_birth_date"],
        }
    raise HTTPException(status_code=response.status_code, detail="Tashqi manbada xatolik!")
