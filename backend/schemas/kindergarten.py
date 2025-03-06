from typing import List, Optional

from pydantic import BaseModel


class OrgDataScheme(BaseModel):
    obl_name: str | None = None
    area_name: str | None = None
    org_name: str | None = None


class OrgLocationScheme(BaseModel):
    id: int | None = None
    location: str | None = None


class EducatorData(BaseModel):
    educator_name: str | None = None
    mtt_name: str | None = None
    main_photo: str | None = None
    passport_photo: str | None = None


class EducatorsDataScheme(BaseModel):
    educators: List[EducatorData] | None = None


class GetDailyFoodResponse(BaseModel):
    groupCount: str
    totalAmount: str
    attendedAmount: str
    notAttendedAmount: str
    status: str
    attendanceEndTime: str
    orderEndTime: str
    attending_kids_count_f: str
    absent_kids_count_f: str
    doc_url: str


class FoodCreateDocument(BaseModel):
    requestId: str | None = None
    shortId: str | None = None
    id: str | None = None
    pin: str | None = None
    documentUrl: str | None = None
    shortLink: str | None = None
    linkExpiredAt: str | None = None
    expireAt: str | None = None


class FoodUniqueDaily(BaseModel):
    attendanceendtime: str | None = None
    orderendtime: str | None = None
    id: str | None = None
    now_date: str | None = None
    now_time: str | None = None


class SetDailyFoodResponse(BaseModel):
    total_count: int | None = 0
    attending_count: int | None = 0
    absent_count: int | None = 0
    create_document: FoodCreateDocument | None = None
    unique_daily: FoodUniqueDaily | None = None
    check: bool | None = None


class DmttEmployeeData(BaseModel):
    id: int
    full_name: str
    tn: str
    pinfl: int
    cn: str | None = None
    bd: str
    pn: str | None = None
    dt: str


class DmttSalaryOrderData(BaseModel):
    id: int
    full_name: str
    pinfl: int
    doc_num: str | None = None
    doc_date: str | None = None
    position: str | None = None
    state_unit: str | None = None
    doc_link: str | None = None
    doc_status: str | None = None
    sign: str | None = None
    order_status: str | None = None
    type: str | None = None


class DmttPositionData(BaseModel):
    id: int | None = None
    name: str | None = None
    name_lotin: str | None = None


class DmttSalaryVocationOrderData(BaseModel):
    id: int
    name: str
    pinfl: int
    doc_date: str | None = None
    doc_num: str | None = None
    doc_link: str | None = None
    doc_status: str | None = None
    sign: str | None = None


class ErrorIdentityCreateData(BaseModel):
    external_id: str | None = None
    error: str | None = None


class SyncTenantEntityResponse(BaseModel):
    mtt_id: int
    name: str
    viloyat: str | None = None
    tuman: str | None = None
    mahlla: str | None = None
    viloyat_kodi: int | None = None
    tuman_kodi: int | None = None
    mahalla_kodi: int | None = None
    inn_stir_pinfl: str | None = None
    location: str | None = None
    phone: str | None = None
    header_name: str | None = None
    header_pinfl: int | None = None
    header_phone: str | None = None
    header_img: str | None = None


class SyncByBBITCountResponse(BaseModel):
    old_count: int | None = 0
    total_count: int | None = 0
    created_count: int | None = 0
    updated_count: int | None = 0
    deleted_count: int | None = 0
    error_list: List[ErrorIdentityCreateData] | None = []


class SuccessResponse(BaseModel):
    status: bool


class NutritionData(BaseModel):
    photo: str | None = None
    photo_date: str | None = None
    nutrition_type: int | None = None


class FoodPhotosResponse(BaseModel):
    nutrition: NutritionData | None = None


class ExtraAttendanceCreate(BaseModel):
    position_id: int
    position_name: str
    week_day: int
    start_time: str
    end_time: str


class DiplomaDataResponse(BaseModel):
    id: int
    pinfl: str
    edu_type_id: int | None = None
    edu_type_name: str | None = None
    institution_type_id: int | None = None
    institution_type_name: str | None = None
    institution_id: int | None = None
    institution_name: str | None = None
    institution_old_name_id: int | None = None
    institution_old_name: str | None = None
    degree_id: int | None = None
    degree_name: str | None = None
    edu_form_id: int | None = None
    edu_form_name: str | None = None
    speciality_id: int | None = None
    speciality_old_id: int | None = None
    speciality_name: str | None = None
    speciality_code: str | None = None
    edu_duration_id: int | None = None
    edu_duration_name: str | None = None
    edu_starting_date: str | None = None
    edu_finishing_date: str | None = None
    diploma_given_date: str | None = None
    diploma_serial_id: int | None = None
    diploma_serial: str | None = None
    diploma_number: str | None = None
    diploma_type_id: int | None = None
    diploma_type_name: str | None = None
    status_id: int | None = None
    status_name: str | None = None


class PassportBaseData(BaseModel):
    pinfl: int
    tin: int | None
    region_id: int | None = None
    district_id: int | None = None
    sur_name: str | None = None
    name: str
    patronymic_name: str | None = None
    full_name: str
    birth_date: str
    gender: int | None = None
    living_place: str | None = None
    address: str | None = None
    given_org: str | None = None
    given_date: str | None = None
    expiration_date: str | None = None
    is_itd: bool
    photo_id: str | None = None
    photo: str | None = None


class PositionData(BaseModel):
    begin_date: str | None = None
    dep_id: int | None = None
    dep_name: str | None = None
    doc_begin_num: str | None = None
    kodp_pn: str | None = None
    org: str | None = None
    org_id: str | None = None
    org_tin: str | None = None
    position: str | None = None
    position_id: int | None = None
    rate: str | None = None


class WorkPositionResponse(BaseModel):
    id: int
    name: str
    partonimic: str | None = None
    pnfl: str
    positions: List[PositionData] | None = None
    result_code: int
    result_message: str | None = None
    surname: str | None = None


class DiplomaData(BaseModel):
    degree_name: str
    institution_name: str
    edu_form_name: str | None = None
    speciality_name: str | None = None
    edu_starting_date: str | None = None
    edu_finishing_date: str | None = None
    diplom_number: str


class WorkPositionData(BaseModel):
    begin_date: str
    end_date: str
    work_experience: str
    speciality_name: str
    org: str
    position: str


class AddEmployeeData(BaseModel):
    passport: str
    birthday: str
    full_name: str
    passport_given_date: str
    passport_finish_date: str
    passport_given_by: str
    pinfl: int
    gender_id: int
    address: str
    phone_number: str | None = None
    region_id: int
    district_id: int
    main_photo: str
    diplomas: List[DiplomaData] | None = None
    positions: List[PositionData] | None = None


class AddEmployeeReturnData(AddEmployeeData):
    mtt_id: int


class SubsidyFoodResponse(BaseModel):
    year: str
    month: int
    subsidy_price: float | None = None
    kid_count: int | None = None
    all_visits: int | None = None
    subsidy_sum: float | None = None


class SubsidyInvMedResponse(BaseModel):
    year: str
    month: int
    subsidy_price_medicine: float | None = None
    subsidy_price_inverter: float | None = None
    payment_medicine: float | None = None
    payment_inverter: float | None = None
    kid_count: int | None = None


class SubsidySalaryResponse(BaseModel):
    year: str
    month: int
    month_working_days: int | None = None
    educator_count: int | None = None
    subsidy_sum: float | None = None


class SubsidyCompResponse(BaseModel):
    year: str
    month: int
    kid_count: int | None = None
    kids_visits_sum: int | None = None
    subsidy_price_electricity: float | None = None
    subsidy_price_gas: float | None = None
    payment_electricity_subsidy: float | None = None
    payment_gas: float | None = None


class PayDocsResponse(BaseModel):
    id: int
    year: str
    month: int
    sub_type: str | None = None
    doc_date: str | None = None
    doc_num: int | None = None
    doc_sum: float | None = None
    uzasbo_reason: str | None = None
    doc_type: str | None = None
    doc_status: str | None = None
    doc_link: str | None = None
    has_link: int | None = None
    uzasbo_state: int | None = None


class GetRekvizitResponse(BaseModel):
    id: int
    full_name: str | None = None
    pinfl: str | None = None
    mfo_id: str | None = None
    bank_name: str | None = None
    account: str | None = None
    doc_link: str | None = None


class DealOrgInfoResponse(BaseModel):
    id: int
    doc_date: str | None = None
    expire_date: str | None = None
    deal_type: str | None = None
    doc_num: str | None = None
    capacity: int | None = None
    cadastre_num: str | None = None
    cadastre_address: str | None = None
    doc_guid: str | None = None
    doc_pin: str | None = None
    sign_date: str | None = None
    mtv_date: str | None = None
    mtv_user: str | None = None
    doc_status: str | None = None
    mtv_status: str | None = None
    mtv_note: str | None = None
    doc_file: str | None = None
    path: str | None = None
    dt: str | None = None


class KidPhotoSignResponse(BaseModel):
    id: int
    full_name: str
    photo: str | None = None
    created_at: str | None = None
    photo_confirm_state: int | None = None
    photo_confirmed_at: str | None = None
    photo_creator: str | None = None
    error_image: str | None = None
    previous_image: str | None = None
    similars_total: int | None = None
    group_id: int | None = None
    group_name: str | None = None


class TransactionData(BaseModel):
    id: int
    date: str
    year: int
    month: int
    note: str | None = None
    credit_sum: float | None = None
    debit_sum: float | None = None
    state: str | None = None


class BillingResponse(BaseModel):
    saldo: float | None = None
    transactions: Optional[List[TransactionData]] = []


class ApplicationAcceptDeedResponse(BaseModel):
    deed_date: str | None = None
    deed_type: str | None = None
    kid_name: str | None = None
    mtt_name: str | None = None
    doc_short_id: str | None = None
    edate: str | None = None


class PKListResponse(BaseModel):
    subsidy_pk_list_id: int | None = None
    full_name: str | None = None
    payment: float | None = None
    pinfl: int | None = None
    card_account: str | None = None
    card_expire: str | None = None
    card_num: str | None = None
    card_type: str | None = None
    educator_id: int | None = None
    note: str | None = None
    pk_status: str | None = None
    status: str | None = None
    doc_type: str | None = None


class RealPayTokenResponse(BaseModel):
    data: str
    code: int
    message: str | None = None


class EducatorResponse(BaseModel):
    user_id: int | None = None
    group_id: int | None = None
    name: str | None = None
    group_name: str | None = None
    emp_type: str | None = None
    post_id: int | None = None
    pinfl: int | None = None
    photo: str | None = None
    created_at: int | None = None
    shtat: str | None = None
    edu: str | None = None
    category: str | None = None
    state: str | None = None
    sal: str | None = None
    account: str | None = None


class KidFeesAmountResponse(BaseModel):
    name: str
    amount: int


class KidFeesPostResponse(BaseModel):
    url: str
