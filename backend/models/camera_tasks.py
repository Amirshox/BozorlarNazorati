from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class SmartCameraTask(BaseModel):
    __tablename__ = "smart_camera_task"
    task_type = Column(String, nullable=False)
    smart_camera_id = Column(Integer, ForeignKey("smart_camera.id"), nullable=False, index=True)
    is_sent = Column(Boolean, default=False)

    users = relationship("SmartCameraTaskUser", back_populates="smart_camera_task")


class SmartCameraTaskResult(BaseModel):
    __tablename__ = "smart_camera_task_result"
    task_id = Column(Integer, ForeignKey("smart_camera_task.id"), nullable=False, index=True)
    status_code = Column(Integer)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)


class SmartCameraTaskUser(BaseModel):
    __tablename__ = "smart_camera_task_user"
    task_id = Column(Integer, ForeignKey("smart_camera_task.id"), nullable=False, index=True)
    visitor_id = Column(Integer, ForeignKey("visitor.id"), nullable=True, index=True)
    identity_id = Column(Integer, ForeignKey("identity.id"), nullable=True, index=True)
    wanted_id = Column(Integer, ForeignKey("wanted.id"), nullable=True, index=True)
    relative_id = Column(Integer, ForeignKey("relative.id"), nullable=True, index=True)

    smart_camera_task = relationship("SmartCameraTask", back_populates="users")
