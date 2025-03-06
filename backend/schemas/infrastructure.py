import datetime
import requests

from enum import IntEnum
from typing import List, Literal, Optional

from pydantic import BaseModel, confloat, conint, validator
from utils.log import timeit


@timeit
def is_device_online(device_id: str) -> bool:
    url = "https://scamera.realsoft.ai/devices/getAllActiveDevices"
    response = requests.get(url)
    if response.status_code == 200:
        all_active_devices: list = response.json()["devices"]
        return device_id in all_active_devices
    return False


# async def get_scamera_active_time(smart_camera_id: int, mongo_db=get_mongo_db()):  # noqa
#     def correct(item: int) -> str:
#         return str(item) if item > 9 else f"0{item}"
#
#     now = datetime.datetime.now()
#     today = now.replace(hour=0, minute=0, second=0, microsecond=0)
#     start_day = today + datetime.timedelta(minutes=10)
#     end_day = today + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
#     query = {"id": smart_camera_id, "created_at": {"$gte": start_day, "$lt": end_day}}
#     try:
#         cursor = await mongo_db.analytics.aggregate([{"$match": query}]).to_list(None)
#     except Exception:
#         return "00:00"
#     if not cursor:
#         return "00:00"
#     minutes = len(cursor) // 2
#     hours = minutes // 60
#     minutes %= 60
#     return f"{correct(hours)}:{correct(minutes)}"


class BuildingBase(BaseModel):
    name: str
    latitude: float
    longitude: float
    tenant_entity_id: int


class BuildingInDB(BuildingBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class RoomBase(BaseModel):
    name: str
    description: Optional[str]
    floor: int
    building_id: int


class RoomInDB(RoomBase):
    id: int
    tenant_id: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CameraSnapshotBase(BaseModel):
    snapshot_url: str
    camera_id: int


class CameraSnapshotInDB(CameraSnapshotBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class CameraBase(BaseModel):
    name: str
    description: Optional[str] = None
    rtsp_url: Optional[str] = None
    vpn_rtsp_url: Optional[str] = None
    stream_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    room_id: int
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    status: Optional[str] = None
    jetson_device_id: Optional[int] = None


class CameraCreate(CameraBase):
    snapshot_url: Optional[str] = None


class CameraInDB(CameraBase):
    id: int
    tenant_id: Optional[int] = None
    tenant_entity_id: Optional[int] = None
    snapshots: Optional[List[CameraSnapshotInDB]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SmartCameraSnapshotInDB(BaseModel):
    id: int
    snapshot_url: str
    smart_camera_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SmartCameraSnapshotFullInDB(SmartCameraSnapshotInDB):
    camera_name: Optional[str] = None
    tenant_entity_name: Optional[str] = None
    building_name: Optional[str] = None
    room_name: Optional[str] = None
    room_description: Optional[str] = None


class SmartCameraProfileBase(BaseModel):
    name: str
    description: Optional[str] = None


class FirmwareBase(BaseModel):
    name: str
    description: Optional[str] = None
    img: str


class FirmwareUpdate(BaseModel):
    name: str
    description: Optional[str] = None


class SmartCameraFirmware(BaseModel):
    firmware_id: int
    smart_camera_id: int


class SmartCameraFirmwareInDB(SmartCameraFirmware):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SmartCameraProfileFirmware(BaseModel):
    profile_id: int
    firmware_id: int


class SmartCameraProfileFirmwareInDB(SmartCameraProfileFirmware):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class SmartCameraBase(BaseModel):
    name: str
    device_id: str
    device_mac: Optional[str] = None
    lib_platform_version: Optional[str] = None
    software_version: Optional[str] = None
    lib_ai_version: Optional[str] = None
    time_stamp: Optional[int] = None
    device_name: Optional[str] = None
    device_ip: Optional[str] = None
    device_lat: Optional[float] = None
    device_long: Optional[float] = None
    stream_url: Optional[str] = None
    rtsp_url: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    room_id: int
    type: Optional[str] = None
    smart_camera_profile_id: int


class TenantEntityForSCamera(BaseModel):
    id: int
    name: str
    external_id: int | None = None

    class Config:
        from_attributes = True


class SmartCameraInDB(SmartCameraBase):
    id: int
    tenant_id: Optional[int] = None
    tenant_entity_id: Optional[int] = None
    last_snapshot_url: Optional[str] = None
    identity_count: Optional[int] = None
    tenant_entity: Optional[TenantEntityForSCamera] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_online: bool = False

    @validator("is_online", always=True)
    def set_is_online(cls, v, values):
        device_id = values.get("device_id")
        if device_id:
            return is_device_online(device_id)
        return False


class SmartCameraHealthList(SmartCameraInDB):
    status: str


class SmartCameraForMap(BaseModel):
    id: Optional[int] = None
    tenant_id: Optional[int] = None
    device_lat: Optional[float] = None
    device_long: Optional[float] = None


class SmartCameraNotCreated(BaseModel):
    device_id: str
    device_mac: str | None = None
    lib_platform_version: str | None = None
    software_version: str | None = None
    lib_ai_version: str | None = None
    device_ip: str | None = None
    device_name: str | None = None


class BazaarSmartCameraSnapshot(BaseModel):
    snapshot_url: Optional[str] = None
    smart_camera_id: Optional[int] = None
    tenant_id: Optional[int] = None
    created_at: Optional[datetime.datetime] = None


class JetsonBase(BaseModel):
    username: str
    password: str
    device_name: Optional[str] = None
    device_id: Optional[str] = None
    device_ip_vpn: Optional[str] = None
    device_stream_url: Optional[str] = None
    room_id: int


class JetsonInDB(JetsonBase):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class JetsonDeviceCameraBase(BaseModel):
    jetson_device_id: int
    camera_id: int


class JetsonDeviceCameraInDB(JetsonDeviceCameraBase):
    cameras: List[CameraInDB]
    jetson_device: JetsonInDB
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class JetsonDeviceSmartCameraBase(BaseModel):
    jetson_device_id: int
    smart_camera_id: int


class JetsonDeviceSmartCameraInDB(JetsonDeviceSmartCameraBase):
    smart_cameras: List[SmartCameraInDB]
    jetson_device: JetsonInDB
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class JetsonDeviceCameraAttachment(BaseModel):
    action_mode: Literal["attach", "detach"]
    camera_id: int
    device_id: int


class JetsonDeviceCameraAttachmentResponse(BaseModel):
    jetson_device_camera_association_id: int
    status: Literal["attached", "detached"]


class CameraDetails(BaseModel):
    id: int
    name: str
    description: str
    stream_url: str
    room_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_active: bool
    rtsp_url: str
    vpn_rtsp_url: str
    longitude: float
    latitude: float
    altitude: int
    tenant_id: int
    jetson_device_id: int


class DeepstreamApp(BaseModel):
    name: str
    path: str
    version: str


class DeepstreamAppCreate(DeepstreamApp):
    pass


class DeepstreamAppUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    version: Optional[str] = None


class JetsonProfile(BaseModel):
    name: str
    username: str
    password: str
    cuda_version: str
    deepstream_version: str
    jetpack_version: str


class JetsonProfileCreate(JetsonProfile):
    pass


class JetsonProfileInDB(JetsonProfile):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class JetsonProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    cuda_version: Optional[str] = None
    deepstream_version: Optional[str] = None
    jetpack_version: Optional[str] = None


class JetsonProfileRegisterDevice(BaseModel):
    jetson_device_id: int
    jetson_profile_id: int


class JetsonDeviceSetUpConfigs(BaseModel):
    jetson_device_id: str
    github_token: str
    jetson_device_manager_url: str


class SetWiredNetworkScheme(BaseModel):
    DHCP: Optional[bool] = True
    IP: str
    subnet_mask: str
    gateway: str
    manual_dns: Optional[bool] = False
    DNS: str
    DNS2: str
    device_mac: str
    webPort: Optional[int] = None


class SetPlatformServerScheme(BaseModel):
    serverAddr: str
    wsServerAddr: str
    wsServerPort: Optional[int] = None
    platformSubCode: Optional[int] = None
    resumeTransf: Optional[bool] = True


class SetVPNConfScheme(BaseModel):
    enable: Optional[bool] = True
    ip_address: str
    vpn_username: str
    vpn_password: str


class SetRebootConfScheme(BaseModel):
    day_week: int
    hour: int
    minute: int
    mode: int  # 0: never, 2: every day, 4: every week


class MyIntEnum(IntEnum):
    open = 1
    close = 0


class SetFaceConfigData(BaseModel):
    FaceQuality: Optional[conint(ge=1, le=10)] = None
    FaceTrackTnable: Optional[MyIntEnum] = None
    MaskDetectEnable: Optional[MyIntEnum] = None
    FaceMiniPixel: Optional[conint(ge=30, le=300)] = None
    FaceMaxPixel: Optional[conint(ge=300, le=700)] = None
    DaEnable: Optional[MyIntEnum] = None
    DetectAreaX: Optional[conint(ge=0, le=1920)] = None
    DetectAreaY: Optional[conint(ge=0, le=1920)] = None
    DetectAreaW: Optional[conint(ge=0, le=1920)] = None
    DetectAreaH: Optional[conint(ge=0, le=1920)] = None
    LivenessEnable: Optional[MyIntEnum] = None
    LivenessThreshold: Optional[confloat(ge=0, le=0.99)] = None
    SnapMode: Optional[conint(ge=0, le=5)] = None
    IntervalFrame: Optional[conint(ge=10, le=1500)] = None
    IntervalTime: Optional[conint(ge=1, le=30)] = None
    SnapNum: Optional[conint(ge=0, le=16)] = None
    UploadMode: Optional[conint(ge=0, le=5)] = None
    ChooseMode: Optional[MyIntEnum] = None
    Yaw: Optional[conint(ge=0, le=100)] = None
    Pitch: Optional[conint(ge=0, le=100)] = None
    Roll: Optional[conint(ge=0, le=100)] = None
    FacePicQuality: Optional[conint(ge=0, le=99)] = None
    PicQuality: Optional[conint(ge=0, le=90)] = None
    SnapFaceArea: Optional[conint(ge=0, le=10)] = None
    MultiFace: Optional[MyIntEnum] = None
    BodyQuality: Optional[conint(ge=0, le=90)] = None
    BodyAreaEx: Optional[conint(ge=0, le=10)] = None
    ExposureMode: Optional[MyIntEnum] = None
    PicUploadMode: Optional[conint(ge=1, le=7)] = None
    WedIrMinFace: Optional[int] = None
    TempEnable: Optional[MyIntEnum] = None
    CompEnable: Optional[MyIntEnum] = None
    CmpThreshold: Optional[conint(ge=50, le=100)] = None
    IoType: Optional[MyIntEnum] = None
    IOOutputTime: Optional[conint(ge=100, le=60000)] = None
    AlarmTempValue: Optional[confloat(ge=30.0, le=104.0)] = None
    TempDetectAreaX: Optional[conint(ge=0, le=1920)] = None
    TempDetectAreaY: Optional[conint(ge=0, le=1920)] = None
    TempDetectAreaW: Optional[conint(ge=0, le=1920)] = None
    TempDetectAreaH: Optional[conint(ge=0, le=1920)] = None
    TempMinPixel: Optional[conint(ge=31, le=1080)] = None
    TempMaxPixel: Optional[conint(ge=31, le=1080)] = None
    IoEnable: Optional[MyIntEnum] = None
    ShowFaceName_N: Optional[MyIntEnum] = None
    IoController: Optional[conint(ge=0, le=5)] = None
    TempType: Optional[MyIntEnum] = None
    strangerFilt: Optional[MyIntEnum] = None
    strangerDay: Optional[conint(ge=1, le=30)] = None


class IdentityAttendanceAnalyticsForSmartCamera(BaseModel):
    uploaded_identity_count: Optional[int] = None
    daily_attendance_count: Optional[int] = None


class SmartCameraWithAnalytics(SmartCameraInDB):
    attendance_count: Optional[int] = None
    avagare_attendance_comp_score: Optional[float] = None


class CustomPaginatedResponseForSmartCamera(BaseModel):
    items: Optional[List[SmartCameraWithAnalytics]] = []
    total: Optional[int] = 0
    page: Optional[int] = 0
    size: Optional[int] = 0
    pages: Optional[int] = 0


class SuccessIdResponse(BaseModel):
    success: bool
    message: str
    id: int
