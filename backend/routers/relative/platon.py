from datetime import datetime
from json import JSONDecodeError
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from auth.oauth2 import get_current_relative
from config import NODAVLAT_BOGCHA_BASE_URL, NODAVLAT_BOGCHA_PASSWORD, NODAVLAT_BOGCHA_USERNAME
from models import Relative
from schemas.identity import SimpleResponse
from schemas.kindergarten import NutritionData
from schemas.relative import (
    GenericResponseSchema,
    MttLocationCloseDistance,
    MttLocationCloseMtt,
    MttLocationCloseMttId,
    MttPhotosSchema,
    ParentFeesKidFoods,
    ParentFeesKidPay,
    ParentFeesKidVisitData,
    ParentFeesMttDataSchema,
    ParentFeesMttStatistics,
    ParentKidApplicationInDB,
    ParentKidApplicationStatus,
    ParentKidSearch,
    ParentSdkAuthResponse,
    RealPaySchema,
    RegionSchemas,
)
from schemas.relative.mtt_location_close import RelativeAttendanceReportData
from services.http_client import HTTPClient

router = APIRouter(prefix="/platon", tags=["platon"])


def get_http_client() -> HTTPClient:
    return HTTPClient(base_url=NODAVLAT_BOGCHA_BASE_URL, auth=(NODAVLAT_BOGCHA_USERNAME, NODAVLAT_BOGCHA_PASSWORD))


@router.get("/parent-fees/mtt/data", response_model=GenericResponseSchema[ParentFeesMttDataSchema])
def get_parent_fees_mtt_data(
    client: HTTPClient = Depends(get_http_client), relative: Relative = Depends(get_current_relative)
):
    endpoint = "parent_fees/mtt/data"
    params = {"pinfl": relative.pinfl}
    response = client.get(endpoint, params=params)
    return response


@router.get("/parent-fees/mtt/statistics", response_model=GenericResponseSchema[ParentFeesMttStatistics])
def get_parent_fees_mtt_statistics(
    mtt_id: int, client: HTTPClient = Depends(get_http_client), relative: Relative = Depends(get_current_relative)
):
    endpoint = "parent_fees/mtt/statistics"
    params = {"mtt_id": mtt_id}
    response = client.get(endpoint, params=params)
    return response


@router.get("/parent-fees/kid/visit/data", response_model=GenericResponseSchema[ParentFeesKidVisitData])
def get_parent_fees_kid_visit_data(
    kid_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    visit_date: Optional[str] = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    params = {"kid_id": kid_id}
    if start_date and end_date:
        params.update({"start_date": start_date, "end_date": end_date})
    elif visit_date:
        params.update({"visit_date": visit_date})
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date is not provided")
    endpoint = "parent_fees/kid/visit/data"
    try:
        response = client.get(endpoint, params=params)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from e
    return response


@router.get("/parent-fees/kid/foods", response_model=GenericResponseSchema[ParentFeesKidFoods])
def get_parent_fees_kid_foods(
    client: HTTPClient = Depends(get_http_client), relative: Relative = Depends(get_current_relative)
):
    endpoint = "parent_fees/kid/foods"
    response = client.get(endpoint)
    return response


@router.get("/parent-fees/kid/payment", response_model=GenericResponseSchema[ParentFeesKidPay])
def get_parent_fees_payment(
    kid_id: int,
    year: int | None = None,
    month: int | None = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "parent_fees/kid/payment"
    params = {"kid_id": kid_id}
    if year:
        params.update({"year": year})
    if month:
        params.update({"month": month})
    response = client.get(endpoint, params=params)
    return response


@router.get("/parent/kid/search", response_model=GenericResponseSchema[ParentKidSearch])
def get_parent_kid_search(
    kid_id: Optional[int] = None,
    pinfl: Optional[str] = None,
    metrics: Optional[str] = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "parent/kid/search"
    if kid_id:
        params = {"kid_id": kid_id}
    elif pinfl:
        params = {"pinfl": pinfl}
    elif metrics:
        params = {"metrics": metrics}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parameter not given!")
    response = client.get(endpoint, params=params)
    return response


@router.get("/mtt/location/close/mtt_id", response_model=MttLocationCloseMttId)
def get_mtt_location_close(
    mtt_id: int = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "mtt/location/close"
    params = {"mtt_id": mtt_id}
    response = client.get(endpoint, params=params)
    return response["data"]


@router.get("/mtt/location/close/distance", response_model=GenericResponseSchema[MttLocationCloseDistance])
def get_mtt_location_close_distance(
    distance: int = None,
    lat: float = None,
    lon: float = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "mtt/location/close"
    params = {"distance": distance, "location": f"{lat},{lon}"}
    response = client.get(endpoint, params=params)
    return response


@router.get("/mtt/location/close/region", response_model=GenericResponseSchema[MttLocationCloseMtt])
def get_mtt_location_close_region(
    region_id: int = None,
    district_id: int = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "mtt/location/close"
    params = {"region_id": region_id, "district_id": district_id}
    response = client.get(endpoint, params=params)
    return response


@router.post("/parent/kid/application")
def parent_kid_application(
    user_id: int,
    kid_id: int,
    relationship: str,
    image: str,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "parent/kid/application"
    data = {"user_id": user_id, "kid_id": kid_id, "relationship": relationship, "image": image}
    client.post(endpoint, data=data)
    return {"message": "success"}


@router.get("/parent/kid/application", response_model=GenericResponseSchema[ParentKidApplicationInDB])
def get_parent_kid_application(user_id: int, client: HTTPClient = Depends(get_http_client)):
    endpoint = "parent/kid/application"
    params = {"user_id": user_id}
    response = client.get(endpoint, params=params)
    return response


@router.get("/parent/kid/application/status", response_model=GenericResponseSchema[ParentKidApplicationStatus])
def get_parent_kid_application_status(application_id: int, client: HTTPClient = Depends(get_http_client)):
    endpoint = "parent/kid/application/status"
    params = {"application_id": application_id}
    response = client.get(endpoint, params=params)
    data = response.get("data", [])
    if isinstance(data, dict):
        data = [data]
    response["data"] = data
    return response


@router.get("/parent/sdk/auth", response_model=ParentSdkAuthResponse)
def get_parent_sdk_auth(
    client: HTTPClient = Depends(get_http_client), relative: Relative = Depends(get_current_relative)
):
    endpoint = "merchant/parent/sdk/auth"
    try:
        data = client.get(endpoint)["data"]
        if data["code"] == 0:
            return data["data"]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=data["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/parent_fees/mtt/photos", response_model=GenericResponseSchema[MttPhotosSchema])
def get_mtt_photos(
    mtt_id: int = None,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "parent_fees/mtt/photos"
    params = {"mtt_id": mtt_id}
    response = client.get(endpoint, params=params)
    return response


@router.get("/payment/ofd/check/{transaction_id}", response_model=RealPaySchema)
def get_realpay_payment(
    transaction_id: str,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "realpay/payment/ofd/check"
    params = {"transaction_id": transaction_id}
    response = client.get(endpoint, params=params)
    try:
        return response["data"]
    except Exception as e:
        print(f"get_realpay_payment: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from e


@router.get("/regions", response_model=List[RegionSchemas])
def get_regions(client: HTTPClient = Depends(get_http_client), relative: Relative = Depends(get_current_relative)):
    endpoint = "regions"
    response = client.get(endpoint)
    return response["data"]


@router.get("/districts/{region_id}", response_model=List[RegionSchemas])
def districts(region_id: int, client: HTTPClient = Depends(get_http_client)):
    endpoint = "districts"
    params = {"region_id": region_id}
    response = client.get(endpoint, params=params)
    return response["data"]


food_photo_description = """nutrition_type\n1 -> nonushta 3 -> tushlik\n4 -> 2-chi tushlik"""


@router.get("/dmtt/food/photos", response_model=List[NutritionData], description=food_photo_description)
def get_food_photos(
    mtt_id: int,
    date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    lang: str = Header("la", alias="Accept-Language"),
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    date_param = date.strftime("%Y-%m-%d") if date else datetime.today().strftime("%Y-%m-%d")
    endpoint = "food/photo"
    params = {"mtt_id": mtt_id, "photo_date": date_param, "lang": lang}
    response = client.get(endpoint, params=params)
    data = response["data"]
    if data["nutrition"]:
        return data["nutrition"]
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ovqat topilmadi!") from None


@router.post("/attendance/report", response_model=SimpleResponse)
def send_attendance_report(
    data: RelativeAttendanceReportData,
    client: HTTPClient = Depends(get_http_client),
    relative: Relative = Depends(get_current_relative),
):
    endpoint = "parent/photo/report"
    json_data = {
        "kid_id": data.kid_id,
        "mtt_id": data.mtt_id,
        "visit_date": data.visit_date,
        "bucket": data.bucket_name,
        "object_name": data.object_name,
        "user_id": relative.id,
    }
    r = client.post(endpoint, data=json_data)
    if r["status"] == 200:
        return {"success": True, "message": None}
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!, Qayta urinib ko'ring!"
    )
