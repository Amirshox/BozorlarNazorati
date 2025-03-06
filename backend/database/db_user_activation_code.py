from fastapi import HTTPException, status
from sqlalchemy import and_, exists
from sqlalchemy.orm.session import Session

from models import TenantAdmin, TenantAdminActivationCode, User, UserActivationCode
from utils.generator import generate_token, no_bcrypt


def create_activation_code(db: Session, user_id: int, activation_code: str):
    if not db.query(exists().where(and_(User.id == user_id, User.is_active))).scalar():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")

    db_activation_code = UserActivationCode(user_id=user_id, code=activation_code, is_active=True)
    db.add(db_activation_code)
    db.commit()
    db.refresh(db_activation_code)

    return db_activation_code


def create_user_activation_code(db: Session, user_id: int):
    activation_code = generate_token(length=32)
    return create_activation_code(db, user_id, activation_code)


def get_by_user_id_all(db: Session, user_id: int):
    return db.query(UserActivationCode).filter_by(user_id=user_id)


def get_activation_code_by_user_id_and_code(db: Session, code: str):
    return db.query(UserActivationCode).filter_by(code=code).first()


def deactivate_activation_code(db: Session, user_id: int, code: str):
    activation_code = db.query(UserActivationCode).filter_by(user_id=user_id, code=code).first()
    if not activation_code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activation code not found")
    activation_code.is_active = False
    db.commit()
    return activation_code


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
