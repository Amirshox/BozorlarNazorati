from typing import Optional

from pydantic import BaseModel


class FaceRecognitionRequestSchema(BaseModel):
    """
    Container for face recognition data
    """

    company_id: Optional[int] = None
    company_type: Optional[str] = None
    request_type: Optional[str] = None
    IP: Optional[str] = None
    device_ip: Optional[str] = None
    device_id: Optional[str] = None
    timestamp: Optional[int] = None
    snap_time: Optional[int] = None
    snap_time_ms: Optional[int] = None
    frpic_name: Optional[str] = None
    user_list: Optional[int]  # 1 is for blacklist 2 is for whitelist ( we use blacklist to store daily visitors)
    mask: Optional[int] = None
    user_name: Optional[str] = "Unknown"
    idcard_number: Optional[str] = None
    user_id: Optional[str] = None
    access_card: Optional[int] = None
    group: Optional[int] = None
    comp_score: Optional[float] = None
    sex: Optional[int] = None
    channel: Optional[int] = None
    image: Optional[str] = None
    fullview_image: Optional[str] = None
    body_image: Optional[str] = None
    face_yaw: Optional[int] = None
    face_pitch: Optional[int] = None
    face_roll: Optional[int] = None
    face_id: Optional[int] = None
    face_quality: Optional[int] = None
    eva_age: Optional[int] = None
    eva_coatstyle: Optional[int] = None
    eva_pans: Optional[int] = None
    eva_bag: Optional[int] = None
    eva_rxstaus: Optional[int] = None
    eva_hair: Optional[int] = None
    car_label: Optional[int] = None
    car_type: Optional[int] = None
    car_color: Optional[int] = None
    event_type: Optional[int] = None  # 1 enter 2 exit
    eva_sex: Optional[str] = None
    sign_tby: Optional[str] = None
