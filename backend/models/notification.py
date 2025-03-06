from sqlalchemy import JSON, Boolean, Column, Integer, String

from models import BaseModel

type_indexes = {1: "KASSA_ID_NOT_FOUND", 2: "ATTENDANCE_REPORT_FROM_PLATON"}


class Notification(BaseModel):
    __tablename__ = "notification"
    sender_id = Column(Integer, nullable=False, index=True)
    sender_type = Column(String, nullable=False, index=True)  # user, relative
    receiver_id = Column(Integer, nullable=False, index=True)
    receiver_type = Column(String, nullable=False, index=True)  # user, relative
    title = Column(String)
    body = Column(String)
    data = Column(JSON)
    image = Column(String)
    external_link = Column(String)
    type_index = Column(Integer, default=0)
    is_sent_via_one_system = Column(Boolean, default=False)
    is_sent_via_platon = Column(Boolean, default=False)
    attempt_count = Column(Integer, default=0)
