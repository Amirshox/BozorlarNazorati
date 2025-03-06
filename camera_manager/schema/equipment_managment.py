from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, conint, confloat


class MyIntEnum(IntEnum):
    open = 1
    close = 0


class PassworSettingsSchema(BaseModel):
    old_password: str
    new_password: str


class PasswordSettingResponseSchema(BaseModel):
    new_password: str
    code: int
    log: str


class EquipmentRebootSchema(BaseModel):
    password: str


class EquipmentRebootResponseSchema(BaseModel):
    code: int
    log: str


class SetWiredNetworkScheme(BaseModel):
    password: str
    DHCP: Optional[bool] = True
    IP: str
    subnet_mask: str
    gateway: str
    manual_dns: Optional[bool] = False
    DNS: str
    DNS2: str
    device_mac: str
    webPort: Optional[int] = 80


class GetWiredNetworkSchemaDHCPClose(BaseModel):
    password: str


class GetWiredNetworkSchemaDHCPOpen(BaseModel):
    password: str


class SuccessResponse(BaseModel):
    code: int
    log: str


class UpgradeFirmwareSchema(BaseModel):
    password: str
    URL: str


class GetSoftwareVersion(BaseModel):
    password: str


class SetRebootConfigSchema(BaseModel):
    password: str
    mode: int
    day_week: Optional[int]
    hour: Optional[int]
    minute: Optional[int]


class SyNCTimeSchema(BaseModel):
    password: str
    time_stamp: str


class SetTheAlignmentModeSchema(BaseModel):
    password: str
    comp_mode: int
    comp_threshold: int


class GetTheAlignmentModeSchema(BaseModel):
    password: str


class SetResumeTransferSchema(BaseModel):
    password: str
    enable: bool


class SetNtpServerSchema(BaseModel):
    password: str
    ntp_server: str
    update_interval: int
    zone: int = 20


class GetTheLogSchema(BaseModel):
    password: str
    log_name: str


class SetPlatformServerSchema(BaseModel):
    password: str
    serverAddr: str
    wsServerAddr: str
    wsServerPort: Optional[int] = 0
    platformSubCode: Optional[int] = 0
    resumeTransf: Optional[bool] = True


class SetVPNConfScheme(BaseModel):
    password: str
    enable: Optional[bool] = True
    ipAddr: str
    userName: str
    vpn_password: str


class SetRebootConfScheme(BaseModel):
    password: str
    day_week: int
    hour: int
    minute: int
    mode: int  # 0: never, 2: every day, 4: every week


class YuntaiControlSchema(BaseModel):
    password: str
    channel: int
    speed_h: int
    speed_v: int
    ptz_cmd: int


class ASnapCommandSchema(BaseModel):
    password: str


class FormatTheDisk(BaseModel):
    password: str


class SetRtmpConf(BaseModel):
    password: str
    channel: int
    RtmpEnable: int
    RtmpServerAddr: str


class SetRtmpConfResponse(BaseModel):
    code: int
    log: str


class SetPtzControl(BaseModel):
    password: str
    speed_h: int
    speed_v: int
    channel: int
    ptz_cmd: int


class SetPtzControlResponse(BaseModel):
    code: int
    log: str
    device_mac: str
    deviceID: str
    device_id: str


class SetFaceConfig(BaseModel):
    password: str
    FaceQuality: Optional[conint(ge=1, le=10)] = 5
    FaceTrackTnable: Optional[MyIntEnum] = MyIntEnum.open
    MaskDetectEnable: Optional[MyIntEnum] = MyIntEnum.close
    FaceMiniPixel: Optional[conint(ge=30, le=300)] = 80
    FaceMaxPixel: Optional[conint(ge=300, le=700)] = 700
    DaEnable: Optional[MyIntEnum] = MyIntEnum.close
    DetectAreaX: Optional[conint(ge=0, le=1920)] = 0
    DetectAreaY: Optional[conint(ge=0, le=1920)] = 0
    DetectAreaW: Optional[conint(ge=0, le=1920)] = 1920
    DetectAreaH: Optional[conint(ge=0, le=1920)] = 1080
    LivenessEnable: Optional[MyIntEnum] = MyIntEnum.close
    LivenessThreshold: Optional[confloat(ge=0, le=0.99)] = 0.98
    SnapMode: Optional[conint(ge=0, le=5)] = 5
    IntervalFrame: Optional[conint(ge=10, le=1500)] = 25
    IntervalTime: Optional[conint(ge=1, le=30)] = 2
    SnapNum: Optional[conint(ge=0, le=16)] = 1
    UploadMode: Optional[conint(ge=0, le=5)] = 0
    ChooseMode: Optional[MyIntEnum] = MyIntEnum.close
    Yaw: Optional[conint(ge=0, le=100)] = 30
    Pitch: Optional[conint(ge=0, le=100)] = 30
    Roll: Optional[conint(ge=0, le=100)] = 30
    FacePicQuality: Optional[conint(ge=0, le=99)] = 99
    PicQuality: Optional[conint(ge=0, le=90)] = 40
    SnapFaceArea: Optional[conint(ge=0, le=10)] = 3
    MultiFace: Optional[MyIntEnum] = MyIntEnum.close
    BodyQuality: Optional[conint(ge=0, le=90)] = 80
    BodyAreaEx: Optional[conint(ge=0, le=10)] = 0
    ExposureMode: Optional[MyIntEnum] = MyIntEnum.close
    PicUploadMode: Optional[conint(ge=1, le=7)] = 1
    WedIrMinFace: Optional[int] = 70
    TempEnable: Optional[MyIntEnum] = MyIntEnum.close
    CompEnable: Optional[MyIntEnum] = MyIntEnum.open
    CmpThreshold: Optional[conint(ge=50, le=100)] = 80
    IoType: Optional[MyIntEnum] = MyIntEnum.close
    IOOutputTime: Optional[conint(ge=100, le=60000)] = 200
    AlarmTempValue: Optional[confloat(ge=30.0, le=104.0)] = 37.99
    TempDetectAreaX: Optional[conint(ge=0, le=1920)] = 0
    TempDetectAreaY: Optional[conint(ge=0, le=1920)] = 0
    TempDetectAreaW: Optional[conint(ge=0, le=1920)] = 0
    TempDetectAreaH: Optional[conint(ge=0, le=1920)] = 0
    TempMinPixel: Optional[conint(ge=31, le=1080)] = 300
    TempMaxPixel: Optional[conint(ge=31, le=1080)] = 900
    IoEnable: Optional[MyIntEnum] = MyIntEnum.open
    ShowFaceName_N: Optional[MyIntEnum] = MyIntEnum.close
    IoController: Optional[conint(ge=0, le=5)] = 0
    TempType: Optional[MyIntEnum] = MyIntEnum.close
    strangerFilt: Optional[MyIntEnum] = MyIntEnum.close
    strangerDay: Optional[conint(ge=1, le=30)] = 7


class GetFaceConfig(BaseModel):
    password: str


class GetFmtSnap(BaseModel):
    password: str
    fmt: int = 0


class GetLogFile(BaseModel):
    password: str
    log_name: str


class GetLogFileResponse(BaseModel):
    resp_type: str
    req_id: int
    code: int
    log: str
    device_id: str
    log_name: str
    log_info: str
