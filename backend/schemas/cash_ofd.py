from typing import List, Optional

from pydantic import BaseModel


class CashOfdsData(BaseModel):
    identity_id: int
    payed_at: str
    paid: int
    payment_type_id: int
    type_id: int
    parent_phone: str
    lat: float
    lon: float


class CommissionInfoDetails(BaseModel):
    TIN: Optional[str] = None
    PINFL: Optional[str] = None


class ItemData(BaseModel):
    cash_id: Optional[str] = None
    Name: str | None = None
    Barcode: Optional[str] = None
    Label: Optional[str] = None
    SPIC: str | None = None
    Units: int | None = None
    GoodPrice: float | None = None
    Price: float | None = None
    Amount: int | None = None
    VAT: int | None = None
    VATPercent: int | None = None
    Discount: int | None = None
    Other: int | None = None
    PackageCode: int | None = None
    PackageName: str | None = None
    CommissionInfo: CommissionInfoDetails


class ExtraInfoData(BaseModel):
    PhoneNumber: str
    Other: Optional[str] = None


class LocationData(BaseModel):
    Latitude: Optional[float] = None
    Longitude: Optional[float] = None


class Model(BaseModel):
    CommitentTin: str | None = None
    ProjectName: str | None = None
    ReceiptId: int | None = None
    ReceivedCash: float | None = None
    ReceivedCard: float | None = None
    TotalVAT: int | None = None
    IsRefund: int | None = None

    Time: str | None

    ReceiptType: int | None = None
    ExtraInfo: ExtraInfoData | None = None
    Location: LocationData | None = None
    Items: List[ItemData] | None = None


class CreateReceiptData(BaseModel):
    Code: int
    Message: str | None = None
    TerminalID: str | None = None
    ReceiptId: int | None = None
    DateTime: str | None = None
    FiscalSign: str | None = None
    QRCodeURL: str | None = None


class CreateReceipt(BaseModel):
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: int
    status: int
    path: Optional[str] = None
    data: CreateReceiptData | None = None
    response: Optional[str] = None


class CashOfdsPostResponse(BaseModel):
    valid_sum: dict = {}
    create_receipt: CreateReceipt | None = None
    commitent_valid: int | None = None
    model: Model | None = None
    valid_sum_is_null: dict = {}


class CashOfdGetResponse(BaseModel):
    p_at: str | None = None
    paid: float | None = None
    full_name: str | None = None
    qr_code_url: str | None = None
    payment_type: str | None = None
