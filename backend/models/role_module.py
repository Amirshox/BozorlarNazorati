from sqlalchemy import Boolean
from models.base import BaseModel
from sqlalchemy import Column, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import ForeignKey
from sqlalchemy.schema import UniqueConstraint


class RoleModule(BaseModel):
    __tablename__ = "role_module"
    role_id = Column(Integer, ForeignKey("role.id"))
    module_id = Column(Integer, ForeignKey("module.id"))
    read = Column(Boolean)
    create = Column(Boolean)
    update = Column(Boolean)
    delete = Column(Boolean)

    role = relationship("Role", back_populates="permissions")

    __table_args__ = (
        UniqueConstraint("role_id", "module_id"),
    )
