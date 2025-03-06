import base64
import logging
import os
import tempfile
from datetime import datetime
from json import JSONDecodeError
from typing import Dict, List, Literal, Optional

import requests
import sentry_sdk
from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Security, UploadFile
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, selectinload
from starlette import status

from auth.oauth2 import get_tenant_entity_user_2
from database import db_identity
from database.database import get_pg_db
from database.db_attendance import get_attendance_stats
from database.db_identity import delete_extra_attendances
from database.minio_client import get_minio_client
from models import District, ExtraAttendance, Identity, TenantEntity
from schemas.cash_ofd import CashOfdGetResponse, CashOfdsData, CreateReceiptData
from schemas.identity import IdentityCreate
from schemas.kindergarten import (
    AddEmployeeData,
    AddEmployeeReturnData,
    ApplicationAcceptDeedResponse,
    BillingResponse,
    DealOrgInfoResponse,
    DiplomaDataResponse,
    DmttEmployeeData,
    DmttPositionData,
    DmttSalaryOrderData,
    DmttSalaryVocationOrderData,
    EducatorResponse,
    EducatorsDataScheme,
    ErrorIdentityCreateData,
    GetDailyFoodResponse,
    GetRekvizitResponse,
    KidFeesAmountResponse,
    KidFeesPostResponse,
    KidPhotoSignResponse,
    NutritionData,
    OrgDataScheme,
    OrgLocationScheme,
    PassportBaseData,
    PayDocsResponse,
    PKListResponse,
    RealPayTokenResponse,
    SetDailyFoodResponse,
    SubsidyCompResponse,
    SubsidyFoodResponse,
    SubsidyInvMedResponse,
    SubsidySalaryResponse,
    SuccessResponse,
    SyncByBBITCountResponse,
    WorkPositionResponse,
)
from schemas.tenant_hierarchy_entity import EntityGroup, TenantEntityInDB
from utils.image_processing import get_image_from_query, make_minio_url_from_image
from utils.kindergarten import correct_lang, get_auth_user, get_user_photo_by_pinfl

logger = logging.getLogger(__name__)

NODAVLAT_BASE_URL = os.getenv("NODAVLAT_BASE_URL")
BASIC_AUTH = {"Authorization": "Basic cmVhbHNvZnRhaTpyZWFsc29mdGFpNDU2NSE="}

PASSPORT_IMAGE_BUCKET = os.getenv("PASSPORT_IMAGE_BUCKET", "passport-image")

global_minio_client = get_minio_client()
if not global_minio_client.bucket_exists(PASSPORT_IMAGE_BUCKET):
    global_minio_client.make_bucket(PASSPORT_IMAGE_BUCKET)

router = APIRouter(prefix="/kindergarten", tags=["Mobile"])

bearer_tokens: Dict[int, Dict[str, datetime]] = {}


def get_auth_token(user_id: int, username="realsoftai", password="realsoftai4565!"):
    if user_id in bearer_tokens:
        token_data = bearer_tokens[user_id]
        for token, token_date in token_data.items():
            now = datetime.now()
            if token_date.day == now.day and token_date.month == now.month:
                return token
    new_token_response = get_auth_user(username, password)
    if new_token_response["success"]:
        bearer_tokens[user_id] = {new_token_response["token"]: datetime.now()}
        return new_token_response["token"]
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=new_token_response["error"])


def base_mtt_request(
    db: Session, path: str, tenant_entity_id: int, lang="la", m="mtt_id", method="GET", params: dict | None = None
):
    params["lang"] = correct_lang(lang) or params.get("lang", "la")
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant entity")
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    if params:
        params.update({m: tenant_entity.external_id})
    else:
        params = {m: tenant_entity.external_id}
    if method == "POST":
        try:
            start_time = datetime.now()
            r = requests.post(url=NODAVLAT_BASE_URL + path, headers=BASIC_AUTH, params=params, timeout=10)
            end_time = datetime.now()
            print(f"spent_time(post.base.{path}): {(end_time - start_time).total_seconds():.2f} s")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Keyinroq urinib ko'ring") from None
    else:
        try:
            start_time = datetime.now()
            r = requests.get(url=NODAVLAT_BASE_URL + path, headers=BASIC_AUTH, params=params, timeout=10)
            end_time = datetime.now()
            print(f"spent_time(get.base.{path}): {(end_time - start_time).total_seconds():.2f} s")
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Keyinroq urinib ko'ring") from None
    try:
        response = r.json()
        if r.status_code == 200:
            return response["data"]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/sync/tenant_entity/info", response_model=TenantEntityInDB)
def sync_tenant_entity_info(
    lang: str = Header("la", alias="Accept-Language"),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    if user.tenant_id == 18 and (not app_version_code or int(app_version_code) < 1169):
        raise HTTPException(
            status_code=status.HTTP_426_UPGRADE_REQUIRED, detail="Ilova versiyasi eski, iltimos ilovani yangilang!"
        )
    lang = correct_lang(lang)
    tenant_entity = db.query(TenantEntity).filter_by(id=user.tenant_entity_id, is_active=True).first()
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity not found")
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    try:
        start_time = datetime.now()
        r = requests.get(
            url=f"{NODAVLAT_BASE_URL}api/v1/realsoftai/mtt/sync?mtt_id={tenant_entity.external_id}&lang={lang}",
            headers=BASIC_AUTH,
            timeout=15,
        )
        end_time = datetime.now()
        print(f"spent_time(sync_mtt): {(end_time - start_time).total_seconds():.2f} s")
    except Exception as e:
        print(f"(sync_mtt)Request error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None
    try:
        response = r.json()
        if r.status_code == 200:
            _ = response["data"]
            district = db.query(District).filter_by(id=tenant_entity.district_id, is_active=True).first()
            t_name = _.get("name", None)
            if t_name and t_name != tenant_entity.name:
                tenant_entity.name = t_name
            tuman_kodi = _.get("tuman_kodi", None)
            if tuman_kodi and tuman_kodi != district.external_id:
                new_district = db.query(District).filter_by(external_id=_["tuman_kodi"], is_active=True).first()
                if new_district:
                    tenant_entity.district_id = new_district.id
                    tenant_entity.region_id = new_district.region_id
                    tenant_entity.country_id = new_district.country_id
            tenant_entity.mahalla_code = _.get("mahalla_kodi", None)
            tenant_entity.tin = _.get("inn_stir_pinfl", None)
            location = _.get("location", None)
            if location:
                lat, lon = location.split(",")
                try:
                    lat, lon = float(lat), float(lon)
                    tenant_entity.lat = lat
                    tenant_entity.lon = lon
                except ValueError:
                    print(f"Invalid location: {_['location']}")
            tenant_entity.phone = _.get("phone", None)
            tenant_entity.director_name = _.get("header_name", None)
            tenant_entity.director_pinfl = str(_.get("header_pinfl", None))
            tenant_entity.director_image = _.get("header_img", None)
            # tenant_entity.allowed_radius = _.get("radius", 1200)
            db.commit()
            db.refresh(tenant_entity)
            groups_query = (
                db.query(
                    Identity.group_id,
                    func.max(Identity.group_name).label("group_name"),
                    func.max(Identity.lat).label("lat").label("lat"),
                    func.max(Identity.lon).label("lon").label("lon"),
                )
                .where(
                    and_(
                        Identity.tenant_entity_id == tenant_entity.id, Identity.identity_group == 0, Identity.is_active
                    )
                )
                .group_by(Identity.group_id)
            )
            result = TenantEntityInDB(**tenant_entity.__dict__)
            groups = [
                EntityGroup(group_id=i.group_id, group_name=i.group_name, lat=i.lat, lon=i.lon)
                for i in groups_query.all()
            ]
            result.groups = groups
            return result
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/sync/kids/by_bbit", response_model=SyncByBBITCountResponse)
async def sync_kids_by_BBIT(
    lang: str = Header("la", alias="Accept-Language"),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    def is_exists(external_id: str, data: list) -> bool:
        return any(external_id == _item["external_id"] for _item in data)

    if user.tenant_id == 18 and (not app_version_code or int(app_version_code) < 1169):
        raise HTTPException(
            status_code=status.HTTP_426_UPGRADE_REQUIRED, detail="Ilova versiyasi eski, iltimos ilovani yangilang!"
        )

    lang = correct_lang(lang)

    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    try:
        start_time = datetime.now()
        r = requests.get(
            url=f"{NODAVLAT_BASE_URL}api/v1/realsoftai/mobile/sync_data?mtt_id={tenant_entity.external_id}&lang={lang}",
            headers=BASIC_AUTH,
            timeout=15,
        )
        end_time = datetime.now()
        print(f"spent_time(sync_kids): {(end_time - start_time).total_seconds():.2f} s")
    except Exception as e:
        print(f"(sync_kids)Request error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None
    try:
        response = r.json()
        if r.status_code == 200:
            result = response["data"]["result"]
            # if result == "WAIT":
            #     raise HTTPException(
            #         status_code=status.HTTP_425_TOO_EARLY,
            #         detail="Ushbu xizmatdan faqat MTT rahbari har 30 daqiqada bir marta foydalanishi mumkin!",
            #     )
            if result == "ERROR":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Sinxronizatsiya qilishda xatolik yuz berdi!"
                )
            elif result == "SUCCESS" or result == "WAIT":
                new_data = response["data"]["data"]
                if not new_data:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="There is no any identity in Tenant Entity!"
                    )
                return_result = SyncByBBITCountResponse()
                identities = (
                    db.query(Identity)
                    .options(selectinload(Identity.extra_attendances))
                    .filter_by(
                        tenant_entity_id=tenant_entity.id,
                        identity_group=0,
                        identity_type="kid",
                        is_active=True,
                        deleted=False,
                    )
                    .all()
                )
                return_result.old_count = len(identities)
                for identity in identities:
                    if not is_exists(str(identity.external_id), new_data):
                        try:
                            identity.is_active = False
                            identity.version += 1
                            db.commit()
                            db.refresh(identity)
                            identities.remove(identity)
                            return_result.deleted_count += 1
                        except Exception as e:
                            new_error = ErrorIdentityCreateData(external_id=identity.external_id, error=f"delete: {e}")
                            return_result.error_list.append(new_error)
                identity_external_ids = [_.external_id for _ in identities]
                for item in new_data:
                    if item["external_id"] in identity_external_ids:
                        u_identity = identities[identity_external_ids.index(item["external_id"])]
                        if (
                            item["pinfl"] != u_identity.pinfl
                            or item["group_id"] != u_identity.group_id
                            or item["group_name"] != u_identity.group_name
                            or item["metrics"] != u_identity.metrics
                            or item["location"] != f"{u_identity.lat},{u_identity.lon}"
                            or item["patronymic_name"] != u_identity.patronymic_name
                        ):
                            u_identity.pinfl = item["pinfl"]
                            u_identity.group_id = item["group_id"]
                            u_identity.group_name = item["group_name"]
                            u_identity.metrics = item["metrics"]
                            u_identity.patronymic_name = item["patronymic_name"]
                            location = item.get("location", None)
                            if location:
                                lat, lon = location.split(",")
                                u_identity.lat = float(lat)
                                u_identity.lon = float(lon)
                            u_identity.version += 1
                            db.commit()
                            return_result.updated_count += 1
                    else:
                        duplicate_identity = (
                            db.query(Identity)
                            .options(selectinload(Identity.extra_attendances))
                            .filter_by(identity_group=0, external_id=item["external_id"], is_active=True, deleted=False)
                            .filter(Identity.tenant_id.in_([1, 18]))
                            .first()
                        )
                        if duplicate_identity:
                            duplicate_identity.is_active = False
                            duplicate_identity.version += 1
                            db.commit()
                            return_result.deleted_count += 1
                        new_identity = IdentityCreate(
                            first_name=item["first_name"],
                            last_name=item["last_name"],
                            pinfl=item["pinfl"],
                            identity_group=0,
                            identity_type="kid",
                            external_id=item["external_id"],
                            group_id=item["group_id"],
                            group_name=item["group_name"],
                            metrics=item["metrics"],
                            patronymic_name=item.get("patronymic_name", None),
                            tenant_entity_id=tenant_entity.id,
                        )
                        try:
                            db_identity.create_identity(db, user.tenant_id, new_identity, username=user.email)
                            return_result.created_count += 1
                        except Exception as e:
                            new_error = ErrorIdentityCreateData(external_id=item["external_id"], error=f"create: {e}")
                            return_result.error_list.append(new_error)
                return_result.total_count = (
                    db.query(Identity.id)
                    .options(selectinload(Identity.extra_attendances))
                    .filter_by(
                        tenant_entity_id=tenant_entity.id,
                        identity_group=0,
                        identity_type="kid",
                        is_active=True,
                        deleted=False,
                    )
                    .count()
                )
                return return_result
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/sync/employees", response_model=SyncByBBITCountResponse)
async def sync_entity_employees(
    lang: str = Header("la", alias="Accept-Language"),
    app_version_code: int = Header(None, alias="App-Version-Code"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    def is_exists(external_id: str, data: list, pinfl: str | None = None) -> bool:
        return any(external_id == _item["external_id"] and pinfl == str(_item["pinfl"]) for _item in data)

    if user.tenant_id == 18 and (not app_version_code or int(app_version_code) < 1169):
        raise HTTPException(
            status_code=status.HTTP_426_UPGRADE_REQUIRED, detail="Ilova versiyasi eski, iltimos ilovani yangilang!"
        )

    lang = correct_lang(lang)

    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    start_time = datetime.now()
    r = requests.get(
        url=f"{NODAVLAT_BASE_URL}api/v1/realsoftai/edu/sync?mtt_id={tenant_entity.external_id}&lang={lang}",
        headers=BASIC_AUTH,
        timeout=15,
    )
    end_time = datetime.now()
    print(f"spent_time(sync_employees): {(end_time - start_time).total_seconds():.2f} s")
    try:
        response = r.json()
        if r.status_code == 200:
            new_data = response["data"]
            if not new_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="There is no any employee in Tenant Entity!"
                )
            return_result = SyncByBBITCountResponse()
            identities = (
                db.query(Identity)
                .filter_by(
                    tenant_entity_id=tenant_entity.id,
                    identity_group=1,
                    identity_type="staff",
                    is_active=True,
                    deleted=False,
                )
                .all()
            )
            return_result.old_count = len(identities)
            for identity in identities:
                if not is_exists(str(identity.external_id), new_data, identity.pinfl):
                    try:
                        delete_extra_attendances(db, identity.id)
                        identity.is_active = False
                        identity.version += 1
                        db.commit()
                        db.refresh(identity)
                        identities.remove(identity)
                        return_result.deleted_count += 1
                    except Exception as e:
                        new_error = ErrorIdentityCreateData(external_id=identity.external_id, error=f"delete: {e}")
                        return_result.error_list.append(new_error)
            identity_external_ids = [_.external_id for _ in identities]
            for item in new_data:
                if item["external_id"] in identity_external_ids:
                    u_identity = identities[identity_external_ids.index(item["external_id"])]
                    if u_identity.external_id == item["external_id"]:
                        if item["attendances"]:
                            positions = item["attendances"].values()
                            delete_extra_attendances(db, u_identity.id)
                            for position in positions:
                                new_position = ExtraAttendance(
                                    identity_id=u_identity.id,
                                    position_id=position["position_id"],
                                    position_name=position["position_name"],
                                    week_day=position["week_day"],
                                    start_time=position["start_time"],
                                    end_time=position["end_time"],
                                )
                                db.add(new_position)
                                db.commit()
                            u_identity.version += 1
                            db.commit()
                        if item["approved_at"] and item["approved_at"] != u_identity.approved_at:
                            u_identity.approved_at = item["approved_at"]
                            u_identity.version += 1
                            db.commit()
                        if item["dismissed_at"] and item["dismissed_at"] != u_identity.dismissed_at:
                            u_identity.dismissed_at = item["dismissed_at"]
                            u_identity.version += 1
                            db.commit()
                        if item["is_active"] is False:
                            u_identity.is_active = False
                            u_identity.version += 1
                            db.commit()
                else:
                    if item["dismissed_at"]:
                        continue
                    duplicate_identity = (
                        db.query(Identity)
                        .filter_by(
                            identity_group=1,
                            tenant_entity_id=tenant_entity.id,
                            external_id=item["external_id"],
                            deleted=False,
                        )
                        .first()
                    )
                    if duplicate_identity:
                        if item["is_active"] is True:
                            if item["approved_at"]:
                                duplicate_identity.approved_at = item["approved_at"]
                            duplicate_identity.is_active = True
                            duplicate_identity.version += 1
                            db.commit()
                        continue
                    new_identity_data = IdentityCreate(
                        first_name=item["first_name"],
                        last_name=item["last_name"],
                        pinfl=item["pinfl"],
                        identity_group=1,
                        identity_type="staff",
                        external_id=item["external_id"],
                        tenant_entity_id=tenant_entity.id,
                    )
                    try:
                        new_identity = db_identity.create_identity(
                            db, user.tenant_id, new_identity_data, username=user.email
                        )
                        return_result.created_count += 1
                        if item["attendances"]:
                            positions = item["attendances"].values()
                            for position in positions:
                                new_position = ExtraAttendance(
                                    identity_id=new_identity.id,
                                    position_id=position["position_id"],
                                    position_name=position["position_name"],
                                    week_day=position["week_day"],
                                    start_time=position["start_time"],
                                    end_time=position["end_time"],
                                )
                                db.add(new_position)
                                db.commit()
                        if item["approved_at"]:
                            new_identity.approved_at = item["approved_at"]
                            db.commit()
                        if item["is_active"] is False:
                            new_identity.is_active = False
                            db.commit()
                    except Exception as e:
                        sentry_sdk.capture_exception(e)
                        new_error = ErrorIdentityCreateData(external_id=item["external_id"], error=f"create: {e}")
                        return_result.error_list.append(new_error)
            return_result.total_count = (
                db.query(Identity.id)
                .filter_by(
                    tenant_entity_id=tenant_entity.id,
                    identity_group=1,
                    identity_type="staff",
                    is_active=True,
                    deleted=False,
                )
                .count()
            )
            return return_result
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/location", response_model=OrgLocationScheme)
def get_location(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/mtt/get_location"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, "mtt", params=params)


@router.get("/org_data", response_model=OrgDataScheme)
def get_organization_data(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/mobile/auth/org_data"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/educators/data", response_model=EducatorsDataScheme)
def get_educators_data(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/mobile/mtt/educators"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/educators/salary")
def get_educators_salary(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/mobile/v1/get/educators"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/educators/cards")
def get_educators_cards(
    year: int,
    month: int,
    educator_id: int,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/mobile/pk_list"
    params = {"year": year, "month": month, "educator_id": educator_id, "lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, "mtt", params=params)


@router.get("/employee/photos")
def get_employee_photos(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/mobile/v2/emp_photo"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/daily_food", response_model=GetDailyFoodResponse)
def get_daily_food(
    date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    date_param = date.strftime("%Y-%m-%d") if date else datetime.today().strftime("%Y-%m-%d")
    path = "api/v1/realsoftai/mobile/daily/food"
    params = {"visit_date": date_param, "lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.post("/daily_food", response_model=SetDailyFoodResponse)
def set_daily_food(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    today = datetime.today()
    total_count, attending_count, absent_count = get_attendance_stats(db, user.tenant_id, user.tenant_entity_id, today)
    path = "api/v1/realsoftai/mobile/daily/food"
    params = {"total_kids": total_count, "attending_kids": attending_count, "absent_kids": absent_count, "lang": lang}
    data = base_mtt_request(db, path, user.tenant_entity_id, lang, method="POST", params=params)
    return SetDailyFoodResponse(
        total_count=total_count,
        attending_count=attending_count,
        absent_count=absent_count,
        create_document=data["create_document"],
        unique_daily=data["unique_daily"],
        check=data["check"],
    )


@router.post("/daily_food/manually", response_model=SetDailyFoodResponse)
def set_daily_food_manually(
    total: int,
    attend: int,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    if attend > total:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attendance must be less than total")
    path = "api/v1/realsoftai/mobile/daily/food"
    params = {"total_kids": total, "attending_kids": attend, "absent_kids": total - attend, "lang": lang}
    data = base_mtt_request(db, path, user.tenant_entity_id, lang, method="POST", params=params)
    return SetDailyFoodResponse(
        total_count=total,
        attending_count=attend,
        absent_count=total - attend,
        create_document=data["create_document"],
        unique_daily=data["unique_daily"],
        check=data["check"],
    )


@router.get("/dmtt/employee", response_model=List[DmttEmployeeData])
def get_dmtt_employee(
    search: Optional[str] = None,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/get/dmtt/employees"
    params = {"lang": lang}
    if search:
        params.update({"search": search})
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/dmtt/salary-order", response_model=List[DmttSalaryOrderData])
def get_dmtt_salary_order(
    type: Literal["HIRING", "TRANSFER", "DISMISSAL"] | None = None,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/get/dmtt/salary-order"
    params = {"lang": lang}
    if type:
        params.update({"type": type})
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/dmtt/position", response_model=List[DmttPositionData])
def get_dmtt_position(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/get/dmtt/position"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/dmtt/salary-vocation-order", response_model=List[DmttSalaryVocationOrderData])
def get_dmtt_salary_vocation_order(
    type: Literal["LABOR_LEAVE", "SICK_LEAVE"] | None = None,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/get/dmtt/salary-vocation-order"
    params = {"lang": lang}
    if type:
        params.update({"type": type})
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


food_photo_description = """nutrition_type\n1 -> nonushta 3 -> tushlik\n4 -> 2-chi tushlik"""


@router.post("/dmtt/food/upload_photo", response_model=SuccessResponse, description=food_photo_description)
def upload_food_photo(
    nutrition_type: int,
    date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    lang: str = Header("la", alias="Accept-Language"),
    file: UploadFile = File(...),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    lang = correct_lang(lang)
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    start_time = datetime.now()
    r = requests.post(
        url=f"{NODAVLAT_BASE_URL}files/upload/category/nutrition_photos?lang={lang}",
        headers=BASIC_AUTH,
        files={"file": (file.filename, file.file, file.content_type)},
    )
    end_time = datetime.now()
    print(f"spent_time(dmtt_upload_food_photo): {(end_time - start_time).total_seconds():.2f} s")
    try:
        response = r.json()
        if r.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
        photo_id = response["id"]
    except JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik yuz berdi! Keyinroq urinib ko'ring"
        ) from None

    date_param = date.strftime("%Y-%m-%d") if date else datetime.today().strftime("%Y-%m-%d")
    path = "api/v1/realsoftai/food/photo"
    params = {
        "photo_date": date_param,
        "photo": photo_id,
        "nutrition_type": nutrition_type,
        "lang": lang,
    }
    base_mtt_request(db, path, user.tenant_entity_id, lang, method="POST", params=params)
    return {"status": True}


@router.get("/dmtt/food/photos", response_model=List[NutritionData], description=food_photo_description)
def get_food_photos(
    date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    date_param = date.strftime("%Y-%m-%d") if date else datetime.today().strftime("%Y-%m-%d")
    path = "api/v1/realsoftai/food/photo"
    params = {"photo_date": date_param, "lang": lang}
    data = base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)
    if data["nutrition"]:
        return data["nutrition"]
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ovqat topilmadi!") from None


@router.get("/dmtt/passport/data", response_model=PassportBaseData)
def get_passport_data(
    passport: str,
    birth_date: datetime = Query(None, description="Date in YYYY-MM-DD format"),
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
    minio_client=Depends(get_minio_client),
):
    lang = correct_lang(lang)
    if not (passport[:2].isalpha() and passport[:2].isupper() and passport[2:].isdigit()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid passport number!")
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    payload = f"series={passport[:2]}&number={passport[2:]}&birth_date={birth_date.strftime('%Y-%m-%d')}&lang={lang}"
    start_time = datetime.now()
    r = requests.get(url=f"{NODAVLAT_BASE_URL}api/v1/realsoftai/get_passport?{payload}", headers=BASIC_AUTH)
    end_time = datetime.now()
    print(f"spent_time(get_passport_data): {(end_time - start_time).total_seconds():.2f} s")
    try:
        response = r.json()
        if r.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ma'lumot topilmadi!") from None
        return_data = response["data"]
        if not return_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data is empty!")
        img_response = get_user_photo_by_pinfl(pinfl=str(return_data["pinfl"]))
        if img_response["success"]:
            try:
                main_image = get_image_from_query(img_response["photo"])
                main_photo_url = make_minio_url_from_image(
                    minio_client, main_image, PASSPORT_IMAGE_BUCKET, str(return_data["pinfl"]), is_check_hd=False
                )
                return_data["photo"] = main_photo_url
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid passport image: {e}"
                ) from e
            file_data = base64.b64decode(img_response["photo"])
            # Create a temporary file with a .jpeg suffix
            with tempfile.NamedTemporaryFile(suffix=".jpeg") as temp_file:
                temp_file.write(file_data)
                temp_file.flush()  # Ensure all data is written to disk
                temp_file.seek(0)
                files = {"file": (temp_file.name, temp_file, "image/jpeg")}
                start_time = datetime.now()
                r2 = requests.post(
                    url=f"{NODAVLAT_BASE_URL}files/upload/category/employee?lang={lang}",
                    headers=BASIC_AUTH,
                    files=files,
                )
                end_time = datetime.now()
                print(f"spent_time(upload/category/employee): {(end_time - start_time).total_seconds():.2f} s")
            try:
                response = r2.json()
                if r2.status_code != 200:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
                return_data["photo_id"] = response["id"]
            except JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik yuz berdi!"
                ) from None
            return return_data
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=img_response["error"])
    except JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik yuz berdi! Keyinroq urinib ko'ring"
        ) from None


@router.get("/dmtt/diploma/data", response_model=List[DiplomaDataResponse])
def get_diploma_data(
    pinfl: str,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    lang = correct_lang(lang)
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    start_time = datetime.now()
    r = requests.get(url=f"{NODAVLAT_BASE_URL}api/v1/realsoftai/diploma?pinfl={pinfl}&lang={lang}", headers=BASIC_AUTH)
    end_time = datetime.now()
    print(f"spent_time(get_diploma_data): {(end_time - start_time).total_seconds():.2f} s")
    try:
        response = r.json()
        if r.status_code == 200:
            return response["data"]["data"]
        return []
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/dmtt/work_position/data", response_model=WorkPositionResponse)
def get_work_position_data(
    pinfl: str,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/mehnat/position"
    params = {"pinfl": pinfl, "lang": lang}
    data = base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)["data"]
    if data["result_code"] != 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=data["result_message"])
    return data


@router.post("/dmtt/add/employee", response_model=SuccessResponse)
def add_employee(
    data: AddEmployeeData,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    lang = correct_lang(lang)
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")
    employee_data = AddEmployeeReturnData(mtt_id=tenant_entity.external_id, **data.dict()).dict()
    start_time = datetime.now()
    r = requests.post(
        url=f"{NODAVLAT_BASE_URL}api/v1/realsoftai/mtt/employee?lang={lang}", headers=BASIC_AUTH, json=employee_data
    )
    end_time = datetime.now()
    print(f"spent_time(add_employee): {(end_time - start_time).total_seconds():.2f} s")
    try:
        response = r.json()
        if r.status_code == 200:
            return {"status": True}
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/nmtt/subsidy/food", response_model=List[SubsidyFoodResponse])
def get_subsidy_food(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/subsidy_food"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/subsidy/inv_med", response_model=List[SubsidyInvMedResponse])
def get_subsidy_inv_med(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/subsidy_inv_med"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/subsidy/salary", response_model=List[SubsidySalaryResponse])
def get_subsidy_salary(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/subsidy_salary"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/subsidy/comp", response_model=List[SubsidyCompResponse])
def get_subsidy_comp(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/subsidy_comp"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/pay_docs", response_model=List[PayDocsResponse])
def get_pay_docs(
    year: int,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/get/pay_docs"
    params = {"year": year, "lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/rekvizit", response_model=GetRekvizitResponse)
def get_rekvizit(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/rekvizit"
    params = {"lang": lang}
    data = base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ma'lumot topilmadi!")
    return data


@router.get("/nmtt/deal/org/info", response_model=List[DealOrgInfoResponse])
def get_deal_org_info(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/deal/org/info"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/kid_photo_sign", response_model=List[KidPhotoSignResponse])
def get_kid_photo_sign(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/kid_photo_sign"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/billing", response_model=BillingResponse)
def get_billing(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/get/billing"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/application/accept/deed", response_model=List[ApplicationAcceptDeedResponse])
def get_application_accept_deed(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/mtt/application/accept/deed"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/nmtt/pk_list", response_model=List[PKListResponse])
def get_pk_list(
    year: int,
    month: int,
    lang: str = Header("la", alias="Accept-Language"),
    educator_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/pk_list"
    params = {"year": year, "month": month, "educator_id": educator_id, "lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.post("/nmtt/real-pay/token", response_model=RealPayTokenResponse)
def get_real_pay_token(
    amount: int,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/real_pay/payment"
    params = {"lang": lang, "amount": amount}
    data = base_mtt_request(db, path, user.tenant_entity_id, lang, method="POST", params=params)
    if data["code"] == 0:
        return data
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=data["message"])


@router.get("/nmtt/educators", response_model=List[EducatorResponse])
def get_educators(
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/mtt/educators"
    params = {"lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.post("/cash/ofds", response_model=CreateReceiptData)
def create_cash_ofds(
    data: CashOfdsData,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/cash/ofds"
    lang = correct_lang(lang)
    tenant_entity = (
        db.query(TenantEntity.id, TenantEntity.external_id).filter_by(id=user.tenant_entity_id, is_active=True).first()
    )
    if not tenant_entity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant entity")
    if not tenant_entity.external_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant entity has no external id")

    identity = (
        db.query(Identity.id, Identity.external_id)
        .filter_by(id=data.identity_id, tenant_entity_id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found!")

    _body = {
        "kid_id": int(identity.external_id),
        "mtt_id": tenant_entity.external_id,
        "payed_at": data.payed_at,
        "paid": data.paid,
        "payment_type_id": data.payment_type_id,
        "type_id": data.type_id,
        "parent_phone": data.parent_phone,
        "username": user.email,
        "location": f"{data.lat},{data.lon}",
    }

    try:
        start_time = datetime.now()
        r = requests.post(url=f"{NODAVLAT_BASE_URL}{path}?lang={lang}", headers=BASIC_AUTH, json=_body, timeout=20)
        end_time = datetime.now()
        print(f"spent_time({path}): {(end_time - start_time).total_seconds():.2f} s")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Keyinroq urinib ko'ring") from None

    try:
        response = r.json()
        if r.status_code == 200:
            return response["data"]["create_receipt"]["data"]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=response["message"]) from None
    except JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tashqi manbada xatolik!") from None


@router.get("/cash/ofd", response_model=List[CashOfdGetResponse])
def get_cash_ofd(
    identity_id: int,
    year: int | None = None,
    month: int | None = None,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realsoftai/cash/ofd"
    identity = (
        db.query(Identity.id, Identity.external_id)
        .filter_by(id=identity_id, tenant_entity_id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found!")
    params = {"kid_id": int(identity.external_id), "lang": lang}
    if year:
        params["year"] = year
    if month:
        params["month"] = month
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.get("/kids/fees", response_model=KidFeesAmountResponse)
def get_kids_fees(
    identity_id: int,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realpay/checkout/kids/fees"
    identity = (
        db.query(Identity.id, Identity.external_id)
        .filter_by(id=identity_id, tenant_entity_id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found!")
    params = {"kid_id": int(identity.external_id), "lang": lang}
    return base_mtt_request(db, path, user.tenant_entity_id, lang, params=params)


@router.post("/kids/fees", response_model=KidFeesPostResponse)
def send_kid_fees(
    identity_id: int,
    amount: int,
    redirect_url: str,
    lang: str = Header("la", alias="Accept-Language"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user_2),
):
    path = "api/v1/realpay/checkout/kids/fees"
    identity = (
        db.query(Identity.id, Identity.external_id)
        .filter_by(id=identity_id, tenant_entity_id=user.tenant_entity_id, is_active=True)
        .first()
    )
    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Identity not found!")
    params = {
        "username": user.email,
        "kid_id": int(identity.external_id),
        "amount": amount,
        "redirect_url": redirect_url,
        "lang": lang,
    }
    checkout_url = base_mtt_request(db, path, user.tenant_entity_id, lang, method="POST", params=params)
    return {"url": checkout_url}
