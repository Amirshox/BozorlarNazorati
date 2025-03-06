from sqlalchemy import text
from sqlalchemy.sql import func
from database.database import Base
from sqlalchemy import Column, Integer, DateTime, Boolean


class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=func.now(), server_default=text('CURRENT_TIMESTAMP'))
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), server_default=text('CURRENT_TIMESTAMP'))
    is_active = Column(Boolean, default=True)
