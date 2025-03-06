from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import Module
from schemas.module import ModuleCreate, ModuleUpdate


def get_modules(db: Session, is_active: bool = True):
    return db.query(Module).filter_by(is_active=is_active)


def get_module(db: Session, pk: int, is_active: bool = True):
    module = db.query(Module).filter_by(id=pk, is_active=is_active).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return module


def create_module(db: Session, module_data: ModuleCreate):
    module_exists = db.query(Module).filter_by(name=module_data.name).first()
    if module_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Module already exists")
    module = Module(name=module_data.name, description=module_data.description)
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


def update_module(db: Session, pk: int, module_data: ModuleUpdate):
    same_module = db.query(Module).filter_by(name=module_data.name).first()
    if same_module and same_module.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Module with name {module_data.name} already exists"
        )
    module_in_db = db.query(Module).filter_by(id=pk, is_active=True).first()
    if not module_in_db:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    if module_data.name:
        module_in_db.name = module_data.name
    if module_data.description:
        module_in_db.description = module_data.description
    db.commit()
    db.refresh(module_in_db)
    return module_in_db


def delete_module(db: Session, pk: int):
    module = db.query(Module).filter_by(id=pk, is_active=True).first()
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    module.is_active = False
    db.commit()
    return module


def get_modules_by_tenat_profile_id(db: Session, tenant_profile_id: int):
    return db.query(Module).filter(Module.tenant_profiles.any(id=tenant_profile_id))
