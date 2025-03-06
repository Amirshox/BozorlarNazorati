from sqlalchemy import Boolean, Column, Integer, String, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY

from models.base import BaseModel


class Roi(BaseModel):
    __tablename__ = "roi"
    name = Column(String)
    description = Column(String)
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=True)
    camera_id = Column(Integer, ForeignKey("camera.id"), nullable=True)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=True)
    color = Column(String)

    people_count_threshold = Column(Integer, nullable=True)
    safe_zone_start_time = Column(Time, nullable=True)
    safe_zone_end_time = Column(Time, nullable=True)
    workspace_type = Column(String, nullable=True)  # worker | client
    detection_object_type = Column(String, nullable=True) # person | car
    shop_id = Column(Integer, nullable=True)

    spot_id = Column(Integer, default=1) # 1- legal place | 2  illegal

    labels = relationship("RoiLabel", back_populates="roi", cascade="all, delete-orphan", lazy="joined")
    points = relationship("RoiPoint", back_populates="roi", lazy="joined")
    camera = relationship("Camera", back_populates="rois")
    smart_camera = relationship("SmartCamera", back_populates="rois")


class RoiLabel(BaseModel):
    __tablename__ = "roi_label"
    roi_id = Column(Integer, ForeignKey("roi.id"))
    label_title = Column(String)  # work-analytics | safe-zone | overcrowd-detection | car-parking

    roi = relationship("Roi", back_populates="labels")


class RoiPoint(BaseModel):
    __tablename__ = "roi_point"

    x = Column(Integer)
    y = Column(Integer)
    order_number = Column(Integer)
    roi_id = Column(Integer, ForeignKey("roi.id"))

    roi = relationship("Roi", back_populates="points")


class Line(BaseModel):
    __tablename__ = "line"
    name = Column(String)
    description = Column(String)
    camera_id = Column(Integer, ForeignKey("camera.id"), nullable=True)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=True)
    type = Column(String)
    dx1 = Column(Integer)
    dy1 = Column(Integer)
    dx2 = Column(Integer)
    dy2 = Column(Integer)
    x1 = Column(Integer)
    y1 = Column(Integer)
    x2 = Column(Integer)
    y2 = Column(Integer)

    camera = relationship("Camera", back_populates="lines")
    smart_camera = relationship("SmartCamera", back_populates="lines")



class ScheduleTemplate(BaseModel):
    __tablename__ = "schedule_template"
    name = Column(String)
    description = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenant.id"))

    schedules = relationship("Schedule", back_populates="template")
    user_schedule_templates = relationship("UserScheduleTemplate", back_populates="template")


class Schedule(BaseModel):
    __tablename__ = "schedule"
    template_id = Column(Integer, ForeignKey("schedule_template.id"), nullable=False)
    weekday = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    template = relationship("ScheduleTemplate", back_populates="schedules")


class UserScheduleTemplate(BaseModel):
    __tablename__ = "user_schedule_template"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("schedule_template.id"), nullable=False)

    user = relationship("User", back_populates="user_schedule_templates")
    template = relationship("ScheduleTemplate", back_populates="user_schedule_templates")


class ErrorSmartCamera(BaseModel):
    __tablename__ = "error_smart_camera"
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    error_type = Column(String)
    error_message = Column(String)
    error_code = Column(Integer)
    version = Column(Integer)
    is_sent = Column(Boolean, default=False)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=True)
    is_resolved = Column(Boolean, default=False)

    # smart_camera = relationship("SmartCamera", back_populates="errors")
    identity = relationship("Identity", back_populates="errors")
    user = relationship("User", back_populates="errors")
