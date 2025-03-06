from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import Module, Role, RoleModule, TenantProfile
from schemas.role_module import RoleModuleCreate, RoleModuleCreateByPermissions, RoleModuleUpdate


def get_role_modules(db: Session, is_active: bool = True):
    return db.query(RoleModule).filter_by(is_active=is_active)


def get_role_module(db: Session, pk: int, is_active: bool = True):
    role_module = db.query(RoleModule).filter_by(id=pk, is_active=is_active).first()
    if not role_module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role module not found")
    return role_module


def create_role_module(db: Session, data: RoleModuleCreate):
    exist = db.query(RoleModule).filter_by(role_id=data.role_id, module_id=data.module_id).first()
    if exist:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role Module already exists")

    if not db.query(exists().where(and_(Role.id == data.role_id, Role.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found")

    if not db.query(exists().where(and_(Module.id == data.module_id, Module.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Module not found")
    new_role_module = RoleModule(
        role_id=data.role_id,
        module_id=data.module_id,
        read=data.read,
        create=data.create,
        update=data.update,
        delete=data.delete,
    )
    db.add(new_role_module)
    db.commit()
    db.refresh(new_role_module)
    return new_role_module


def update_role_module(db: Session, pk: int, data: RoleModuleUpdate):
    role_module = db.query(RoleModule).filter_by(id=pk).first()
    if not role_module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role Module not found")
    if data.read:
        role_module.read = data.read
    if data.create:
        role_module.create = data.create
    if data.update:
        role_module.update = data.update
    if data.delete:
        role_module.delete = data.delete
    db.commit()
    db.refresh(role_module)
    return role_module


def delete_role_module(db: Session, pk: int):
    role_module = db.query(RoleModule).filter_by(id=pk, is_active=True).first()
    if not role_module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role Module not found")
    role_module.is_active = False
    db.commit()
    return role_module


def create_role_module_by_permissions(db: Session, data: RoleModuleCreateByPermissions):
    module_ids = [permission.module_id for permission in data.permissions]
    result = db.query(Module).where(Module.id.in_(module_ids))
    count = result.count()
    if count != len(module_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Permission id do not exist")
    role_exists = db.query(Role).filter_by(name=data.name, is_active=True).first()
    if role_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    if not db.query(exists().where(and_(TenantProfile.id == data.tenant_profile_id, TenantProfile.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant profile not found")
    role = Role(name=data.name, description=data.description, tenant_profile_id=data.tenant_profile_id)
    db.add(role)
    db.commit()
    db.refresh(role)
    if data.permissions:
        for permission in data.permissions:
            module = db.query(Module).filter_by(id=permission.module_id, is_active=True).first()
            role_module = RoleModule(
                role_id=role.id,
                module_id=module.id,
                read=permission.read,
                create=permission.create,
                update=permission.update,
                delete=permission.delete,
            )
            db.add(role_module)
            db.commit()
            db.refresh(role_module)
    return role


def update_role_module_by_permissions(db: Session, pk: int, data: RoleModuleCreateByPermissions):
    role = db.query(Role).filter_by(id=pk, is_active=True).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    same_name_role = db.query(Role).filter_by(name=data.name, is_active=True).first()
    if same_name_role and same_name_role.id != pk:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Role already exists with name {data.name}"
        )
    if not db.query(exists().where(and_(TenantProfile.id == data.tenant_profile_id, TenantProfile.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant profile not found")
    if data.name:
        role.name = data.name
    if data.description:
        role.description = data.description
    if data.tenant_profile_id:
        role.tenant_profile_id = data.tenant_profile_id
    db.commit()
    db.refresh(role)
    if data.permissions:
        for permission in data.permissions:
            role_module = (
                db.query(RoleModule).filter_by(role_id=pk, module_id=permission.module_id, is_active=True).first()
            )
            if role_module:
                if permission.read:
                    role_module.read = permission.read
                if permission.create:
                    role_module.create = permission.create
                if permission.update:
                    role_module.update = permission.update
                if permission.delete:
                    role_module.delete = permission.delete
                db.commit()
                db.refresh(role_module)
    return role
