import os

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm.session import Session
from starlette.requests import Request

from database import db_user
from database.database import get_pg_db
from database.db_attestation import create_attestation2
from database.db_user import create_tenant_entity_user, get_user_by_pinfl
from database.hash import Hash
from models import TenantAdmin, TenantEntity, ThirdPartyIntegration, User
from models.user import AccessToken, RefreshToken
from schemas.tenant_admin import TenantAdminInDB
from schemas.user import UserCreate, UserInDBBase
from services.relative.login import relative_login_service
from utils import kindergarten
from utils.generator import no_bcrypt, short_uuid

from .oauth2 import (
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    get_current_tenant_admin,
    get_tenant_entity_user,
)

SYSADMIN = os.getenv("SYSADMIN", "sysadmin")
ADMIN = os.getenv("ADMIN", "admin")
UNI_PASS_KEY = os.getenv("UNI_PASS_KEY")

router = APIRouter(tags=["authentication"])


class RefreshTokenData(BaseModel):
    token: str


@router.post("/refresh_token")
def _refresh_token(request: Request, data: RefreshTokenData, db: Session = Depends(get_pg_db)):
    headers = request.headers
    token_id = short_uuid()
    app_version_code = headers.get("App-Version-Code", None)
    app_version_name = headers.get("App-Version-Name", None)
    device_id = headers.get("Device-Id", None)
    device_ip = headers.get("Device-IP", None)
    device_name = headers.get("Device-Name", None)
    device_model = headers.get("Device-Model", None)
    app_source = headers.get("X-App-Source", None)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")
        token_type = payload.get("type")
        refresh_id = payload.get("token_id")
        if not username:
            raise credentials_exception from None
        if token_type != "refresh":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Permission denied") from None
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e
    user = db_user.get_tenant_entity_user_by_email(db, username)
    if not user:
        raise credentials_exception from None
    access_token = create_access_token(data={"sub": user.email, "token_id": token_id})
    db_access_token = AccessToken(
        user_id=user.id,
        token=access_token,
        unique_id=token_id,
        app_version_code=int(app_version_code) if app_version_code else None,
        app_version_name=app_version_name,
        device_id=device_id,
        device_ip=device_ip,
        device_name=device_name,
        device_model=device_model,
        app_source=app_source,
        refresh_id=refresh_id,
    )
    db.add(db_access_token)
    db.commit()
    db.refresh(db_access_token)

    refresh_token = create_refresh_token(data={"username": user.email, "token_id": token_id})
    db_refresh_token = RefreshToken(user_id=user.id, token=refresh_token, refresh_id=refresh_id)
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.email,
        "user_type": "customer_user",
        "tenant_id": user.tenant_id,
        "attestation": None,
    }


@router.post("/new_access_token")
def new_access_token(request: Request, data: RefreshTokenData, db: Session = Depends(get_pg_db)):
    headers = request.headers
    token_id = short_uuid()
    app_version_code = headers.get("App-Version-Code", None)
    app_version_name = headers.get("App-Version-Name", None)
    device_id = headers.get("Device-Id", None)
    device_ip = headers.get("Device-IP", None)
    device_name = headers.get("Device-Name", None)
    device_model = headers.get("Device-Model", None)
    app_source = headers.get("X-App-Source", None)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(data.token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception from None
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e
    user = db_user.get_tenant_entity_user_by_email(db, username)
    if not user:
        raise credentials_exception from None
    access_token = create_access_token(data={"sub": user.email, "token_id": token_id})
    db_access_token = AccessToken(
        user_id=user.id,
        token=access_token,
        unique_id=token_id,
        app_version_code=int(app_version_code) if app_version_code else None,
        app_version_name=app_version_name,
        device_id=device_id,
        device_ip=device_ip,
        device_name=device_name,
        device_model=device_model,
        app_source=app_source,
    )
    db.add(db_access_token)
    db.commit()
    db.refresh(db_access_token)

    refresh_token = create_refresh_token(data={"username": user.email, "token_id": token_id})
    db_refresh_token = RefreshToken(user_id=user.id, token=refresh_token)
    db.add(db_refresh_token)
    db.commit()
    db.refresh(db_refresh_token)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.email,
        "user_type": "customer_user",
        "tenant_id": user.tenant_id,
        "attestation": None,
    }


@router.post("/token")
def get_token(request: Request, oauth2_form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_pg_db)):
    headers = request.headers
    oauth2_form.username = oauth2_form.username.strip(" ")
    oauth2_form.password = oauth2_form.password.strip(" ")
    if oauth2_form.username == SYSADMIN:
        if oauth2_form.password != ADMIN:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        access_token = create_access_token(data={"sub": oauth2_form.username, "scopes": oauth2_form.scopes})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": oauth2_form.username,
            "user_type": "system_admin",
        }
    tenant_admin = db.query(TenantAdmin).filter_by(email=oauth2_form.username).first()
    if tenant_admin:
        if not Hash.verify(tenant_admin.password, oauth2_form.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
        access_token = create_access_token(data={"sub": tenant_admin.email, "scopes": oauth2_form.scopes})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "username": tenant_admin.email,
            "user_type": "tenant_admin",
        }
    user = db.query(User).filter_by(email=oauth2_form.username).first()
    incorrect_password = False
    token_id = short_uuid()
    integrity_token = headers.get("integrity-token", None)
    app_version_code = headers.get("App-Version-Code", None)
    app_version_name = headers.get("App-Version-Name", None)
    device_id = headers.get("Device-Id", None)
    device_ip = headers.get("Device-IP", None)
    device_name = headers.get("Device-Name", None)
    device_model = headers.get("Device-Model", None)
    app_source = headers.get("X-App-Source", None)
    if user:
        if not Hash.verify(user.password, oauth2_form.password):
            incorrect_password = True
        else:
            access_token = create_access_token(
                data={"sub": user.email, "token_id": token_id, "scopes": oauth2_form.scopes}
            )
            db_access_token = AccessToken(
                user_id=user.id,
                token=access_token,
                unique_id=token_id,
                integrity_token=integrity_token,
                app_version_code=int(app_version_code) if app_version_code else None,
                app_version_name=app_version_name,
                device_id=device_id,
                device_ip=device_ip,
                device_name=device_name,
                device_model=device_model,
                app_source=app_source,
            )
            db.add(db_access_token)
            db.commit()
            db.refresh(db_access_token)

            refresh_token = create_refresh_token(data={"username": user.email, "token_id": token_id})
            db_refresh_token = RefreshToken(user_id=user.id, token=refresh_token)
            db.add(db_refresh_token)
            db.commit()
            db.refresh(db_refresh_token)

            user.pwd = oauth2_form.password
            db.commit()
            db.refresh(user)

            attestation, attestation_data = create_attestation2(db, user.id, token_id, integrity_token, device_id)
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user_id": user.id,
                "username": user.email,
                "user_type": "customer_user",
                "tenant_id": user.tenant_id,
                "attestation": attestation_data,
            }
    mtt_user_response = kindergarten.get_auth_user(oauth2_form.username, oauth2_form.password)
    if mtt_user_response["success"]:
        mtt_user = mtt_user_response["data"]
        tenant_entity = (
            db.query(TenantEntity)
            .filter_by(external_id=mtt_user["mtt_id"], is_active=True)
            .filter(TenantEntity.tenant_id.in_([1, 18]))
            .first()
        )
        if tenant_entity:
            if incorrect_password:
                user.password = no_bcrypt(oauth2_form.password)
                user.pwd = oauth2_form.password
                db.commit()
                db.refresh(user)

                access_token = create_access_token(
                    data={"sub": oauth2_form.username, "token_id": token_id, "scopes": oauth2_form.scopes}
                )
                db_access_token = AccessToken(
                    user_id=user.id,
                    token=access_token,
                    unique_id=token_id,
                    integrity_token=integrity_token,
                    app_version_code=int(app_version_code) if app_version_code else None,
                    app_version_name=app_version_name,
                    device_id=device_id,
                    device_ip=device_ip,
                    device_name=device_name,
                    device_model=device_model,
                    app_source=app_source,
                )
                db.add(db_access_token)
                db.commit()
                db.refresh(db_access_token)

                refresh_token = create_refresh_token(data={"username": oauth2_form.username, "token_id": token_id})
                db_refresh_token = RefreshToken(user_id=user.id, token=refresh_token)
                db.add(db_refresh_token)
                db.commit()
                db.refresh(db_refresh_token)

                attestation, attestation_data = create_attestation2(db, user.id, token_id, integrity_token, device_id)
                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                    "user_id": user.id,
                    "username": user.email,
                    "user_type": "customer_user",
                    "tenant_id": user.tenant_id,
                    "attestation": attestation_data,
                }
            else:
                new_user_data = UserCreate(
                    email=oauth2_form.username,
                    password=oauth2_form.password,
                    first_name=mtt_user["firstname"],
                    last_name=mtt_user["lastname"],
                    phone=str(mtt_user["phone"]),
                    pinfl=str(mtt_user["pinfl"]),
                    tenant_entity_id=tenant_entity.id,
                    role_id=3,
                )
                new_user = create_tenant_entity_user(db, tenant_entity.tenant_id, new_user_data)
                if new_user:
                    access_token = create_access_token(
                        data={"sub": oauth2_form.username, "token_id": token_id, "scopes": oauth2_form.scopes}
                    )
                    db_access_token = AccessToken(
                        user_id=new_user.id,
                        token=access_token,
                        unique_id=token_id,
                        integrity_token=integrity_token,
                        app_version_code=int(app_version_code) if app_version_code else None,
                        app_version_name=app_version_name,
                        device_id=device_id,
                        device_ip=device_ip,
                        device_name=device_name,
                        device_model=device_model,
                        app_source=app_source,
                    )
                    db.add(db_access_token)
                    db.commit()
                    db.refresh(db_access_token)

                    refresh_token = create_refresh_token(data={"username": oauth2_form.username, "token_id": token_id})
                    db_refresh_token = RefreshToken(user_id=new_user.id, token=refresh_token)
                    db.add(db_refresh_token)
                    db.commit()
                    db.refresh(db_refresh_token)

                    attestation, attestation_data = create_attestation2(
                        db, new_user.id, token_id, integrity_token, device_id
                    )
                    return {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "token_type": "bearer",
                        "user_id": new_user.id,
                        "username": new_user.email,
                        "user_type": "customer_user",
                        "tenant_id": new_user.tenant_id,
                        "attestation": attestation_data,
                    }
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")


@router.post("/system_token")
def get_system_token(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_pg_db)):
    if request.username != SYSADMIN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if request.password != ADMIN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    access_token = create_access_token(data={"sub": request.username, "scopes": request.scopes})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": request.username,
        "user_type": "system_admin",
    }


@router.post("/tenant_token")
def get_tenant_admin_token(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_pg_db)):
    user = db.query(TenantAdmin).filter_by(email=request.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not Hash.verify(user.password, request.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    access_token = create_access_token(data={"sub": user.email, "scopes": request.scopes})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.email,
        "user_type": "tenant_admin",
    }


@router.post("/third_party_token")
def get_third_party_token(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_pg_db)):
    user = db.query(ThirdPartyIntegration).filter_by(username=request.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not Hash.verify(user.password, request.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    access_token = create_access_token(data={"sub": user.username, "scopes": request.scopes})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "user_type": "third_party_integration",
    }


@router.get("/tenant_admin_me", response_model=TenantAdminInDB)
def get_tenant_admin_me(user: TenantAdmin = Security(get_current_tenant_admin)):
    return user


@router.post("/user_token")
def get_user_token(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_pg_db)):
    request.username = request.username.strip(" ")
    request.password = request.password.strip(" ")
    user = db.query(User).filter_by(email=request.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not Hash.verify(user.password, request.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")
    access_token = create_access_token(data={"sub": user.email, "scopes": request.scopes})
    refresh_token = create_refresh_token(data={"username": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": user.email,
        "user_type": "customer_user",
    }


@router.get("/customer_user_me", response_model=UserInDBBase)
def get_customer_user_me(user: User = Security(get_tenant_entity_user)):
    return user


class RelativeLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    username: str
    user_type: str


@router.post("/relative_token", response_model=RelativeLoginResponse)
def user_set_password(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_pg_db)):
    return relative_login_service(db, request.username, request.password)


@router.post("/uni-pass")
def uni_pass(client_id: str, token: str, db: Session = Depends(get_pg_db)):
    try:
        data = jwt.decode(token, UNI_PASS_KEY, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = get_user_by_pinfl(db, data["pinfl"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"username": user.email})
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "username": user.email,
        "user_type": "customer_user",
    }
