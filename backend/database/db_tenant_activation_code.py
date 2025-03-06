from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import TenantAdmin, TenantAdminActivationCode, User, UserActivationCode
from utils.generator import generate_token, no_bcrypt


def create_tenant_admin_activation_code(db: Session, tenant_admin_activation_code: str, tenant_admin_id: int):
    db_tenant_admin_activation_code = TenantAdminActivationCode(
        code=tenant_admin_activation_code, tenant_admin_id=tenant_admin_id, is_active=True
    )
    db.add(db_tenant_admin_activation_code)
    db.commit()
    db.refresh(db_tenant_admin_activation_code)
    return db_tenant_admin_activation_code


def create_activation_code(db: Session, tenant_admin_id: int):
    code = generate_token(length=32)
    return create_tenant_admin_activation_code(db, code, tenant_admin_id)


def get_tenant_admin_activation_codes_by_tenant_admin_id_active(db: Session, tenant_admin_id: int):
    return db.query(TenantAdminActivationCode).filter_by(tenant_admin_id=tenant_admin_id, is_active=True)


def get_tenant_admin_activation_code_by_code(db: Session, code: str):
    return db.query(TenantAdminActivationCode).filter_by(code=code).first()


def get_activation_code_and_update_password(db: Session, code: str, new_password: str):
    activation_code = db.query(UserActivationCode).filter_by(code=code).first()
    platform_user = None
    if activation_code:
        platform_user = db.query(User).filter_by(id=activation_code.user_id).first()
        if not activation_code.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation code is already used")

    if not activation_code:
        activation_code = db.query(TenantAdminActivationCode).filter_by(code=code).first()
        if not activation_code:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation code not found")
        if not activation_code.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation code is already used")
        platform_user = db.query(TenantAdmin).filter_by(id=activation_code.tenant_admin_id).first()

    if not platform_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    activation_code.is_active = False
    db.commit()
    platform_user.password = no_bcrypt(new_password)
    platform_user.is_active = True
    db.commit()
    return platform_user


def get_by_admin_id_all(db: Session, tenant_admin_id: int):
    return db.query(TenantAdminActivationCode).filter_by(tenant_admin_id=tenant_admin_id, is_active=True).all()


def deactivate_activation_code(db: Session, code: str):
    activation_code = db.query(TenantAdminActivationCode).filter_by(code=code, is_active=True).first()
    if not activation_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation code not found")
    activation_code.is_active = False
    db.commit()
    return activation_code
