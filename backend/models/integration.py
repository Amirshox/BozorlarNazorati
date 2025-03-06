from sqlalchemy import Column, Integer, String
from sqlalchemy.sql.schema import ForeignKey

from models.base import BaseModel


class Integrations(BaseModel):
    __tablename__ = "integrations"

    tenant_id = Column(Integer, ForeignKey("tenant.id"))
    module_id = Column(Integer, ForeignKey("module.id"))
    callback_url = Column(String, nullable=False)
    identity_callback_url = Column(String, nullable=True)
    auth_type = Column(String)  # basic or jwt or None
    username = Column(String)
    password = Column(String)
    token = Column(String)
    token_type = Column(String)  # default=bearer
