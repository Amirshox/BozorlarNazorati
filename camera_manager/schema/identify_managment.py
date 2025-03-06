from typing import List
from pydantic import BaseModel


class GetSnapPic(BaseModel):
    password: str
    frip_name: str
    picture_type: int = 1
    recv_url: str


class GetSNapPicList(BaseModel):
    password: str
    start_time: int
    end_time: int
    max_number: int
    picture_type: int
    recv_url: str


class Snap(BaseModel):
    frpic_name: str
    ret: int


class GetSnapPicListResponse(BaseModel):
    snap_number: int
    snap_list: List[Snap]
    code: int
    log: str


class GetRecordFile(BaseModel):
    password: int
    start_time: int
    end_time: int
    recv_url: str


class GetRecordFileResponse(BaseModel):
    file: str
    code: int
    log: str


class GetpicRecognition(BaseModel):
    password: str
    image_type: str
    image_content: str
    min_fscore: float = 70.0
    max_result_num: int = 1
# response
# {
# "user_list_num": 1,
# "user_list": [ {
# "comp_score": 88.527218, "user_id": "10407",
# "user_name": "test9", "id_card_num": "", "access_card": 1, "user sex": 1, "create_time": "", "phone_number": "",
# "department": "", "user_info": "",
# "group": 2, "user_list": 2,
# "sim_seid": "", "auth_start_time": 0,
# "auth_end_time": 0, "time_mode": 0, "finger_print": 0,
# "group_plus": 0 }
# ].
# "resp_type": "picRecognition",
# "request_id": "123456", "code": 0,
# "device_mac": "bc-07-18-00-d5-da", "deviceID": "H01000117110100010886",
# "device_id": "H01000117110100010886", "log": "'picRecognition' success",
# device_ip: "192.168.1.59",
# "sign_tby": "4cb7fd92942e341afcc9fe479f176bc7"
# }


class UserList(BaseModel):
    comp_score: float
    user_id: str
    user_name: str
    id_card_num: str
    access_card: int
    user_sex: int
    create_time: str
    phone_number: str
    department: str
    user_info: str
    user_list: int
    sim_seid: str
    auth_start_time: int
    auth_end_time: int
    time_mode: int
    finger_print: int
    group_plus: int


class GetpicRecognitionResponse(BaseModel):
    user_list_num: int
    user_list: List[UserList]
    code: int
    log: str
    resp_type: str
    request_id: str
    device_mac: str
    deviceID: str
    device_id: str
    device_ip: str
    sign_tby: str
