from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class Visitor(BaseModel):
    __tablename__ = "visitor"
    photo = Column(String, nullable=False)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=False)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"))
    is_uploaded = Column(Boolean, default=False)


class VisitorAttendance(BaseModel):
    __tablename__ = "visitor_attendance"
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=False)
    attendance_type = Column(String, default="enter")
    attendance_datetime = Column(DateTime)
    snapshot_url = Column(String)
    background_image_url = Column(String)
    body_image_url = Column(String)
    visitor_id = Column(Integer, ForeignKey("visitor.id"), nullable=True)
