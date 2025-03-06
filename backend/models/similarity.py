from sqlalchemy import Column, Float, ForeignKey, Integer, String

from models.base import BaseModel


class SimilarityMainPhotoInArea(BaseModel):
    __tablename__ = "similarity_main_photo_in_area"
    identity_id = Column(Integer, ForeignKey("identity.id"), index=True)
    image_url = Column(String)
    version = Column(Integer)
    similar_identity_id = Column(Integer)
    similar_image_url = Column(String)
    similar_version = Column(Integer)
    distance = Column(Float)


class SimilarityMainPhotoInEntity(BaseModel):
    __tablename__ = "similarity_main_photo_in_entity"
    identity_id = Column(Integer, ForeignKey("identity.id"), index=True)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), index=True)
    image_url = Column(String)
    version = Column(Integer)
    similar_identity_id = Column(Integer)
    similar_image_url = Column(String)
    similar_tenant_entity_id = Column(Integer)
    similar_version = Column(Integer)
    distance = Column(Float)


class SimilarityAttendancePhotoInArea(BaseModel):
    __tablename__ = "similarity_attendance_photo_in_area"
    identity_id = Column(Integer, ForeignKey("identity.id"), index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), index=True)
    image_url = Column(String)
    capture_timestamp = Column(Integer)
    similar_attendance_id = Column(Integer)
    similar_image_url = Column(String)
    similar_capture_timestamp = Column(Integer)
    distance = Column(Float)


class SimilarityAttendancePhotoInEntity(BaseModel):
    __tablename__ = "similarity_attendance_photo_in_entity"
    identity_id = Column(Integer, ForeignKey("identity.id"), index=True)
    tenant_entity_id = Column(Integer, ForeignKey("tenant_entity.id"), index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), index=True)
    image_url = Column(String)
    capture_timestamp = Column(Integer)
    similar_attendance_id = Column(Integer)
    similar_image_url = Column(String)
    similar_capture_timestamp = Column(Integer)
    distance = Column(Float)
