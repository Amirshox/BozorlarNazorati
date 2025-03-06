import os
import time
from datetime import datetime, timedelta
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
from fastapi.param_functions import Depends
from fastapi.security import HTTPBearer, OAuth2PasswordBearer, SecurityScopes
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.status import HTTP_400_BAD_REQUEST

from database import db_relative, db_tenant_admin, db_third_party, db_user
from database.database import get_pg_db
from schemas.auth import TokenData

scopes = {
    "me": "Read information about the current user.",
    "admin:read": "Read information about the admin.",
    "admin:write": "Write information about the admin.",
    "user:read": "Read information about the user.",
    "user:write": "Write information about the user.",
    "fleet:read": "Read information about the fleet.",
    "fleet:write": "Write information about the fleet.",
    "module:read": "Read information about the module.",
    "module:write": "Write information about the module.",
    "camera:read": "Read information about the camera.",
    "camera:write": "Write information about the camera.",
    "snapshot:read": "Read information about the snapshot.",
    "snapshot:write": "Write information about the snapshot.",
    "config:read": "Read information about the config.",
    "config:write": "Write information about the config.",
    "roi_analytics:read": "Read information about the roi_analytics.",
    "roi_analytics:write": "Write information about the roi_analytics.",
    "line_crossing_analytics:read": "Read information about the line_crossing_analytics.",
    "line_crossing_analytics:write": "Write information about the line_crossing_analytics.",
}

load_dotenv(find_dotenv())
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 183 * 24 * 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", 365))
attendance_token_extra_time = 5 * 24 * 60 * 60

SYSADMIN = os.getenv("SYSADMIN", "sysadmin")
SYSADMIN_PASSWORD = os.getenv("SYSADMIN_PASSWORD", "sysadmin")


class CustomOAuth2PasswordBearer(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> Optional[str]:
        authorization = request.headers.get("Authorization")
        scheme, param = get_authorization_scheme_param(authorization)
        if not authorization or scheme.lower() != "bearer":
            if self.auto_error:
                raise HTTPException(
                    status_code=HTTP_400_BAD_REQUEST,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        return param


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


oauth2_scheme = CustomOAuth2PasswordBearer(tokenUrl="user_token", scopes=scopes)
security = HTTPBearer()


def get_tenant_entity_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_pg_db),  # noqa
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception from None
        iat = payload.get("iat", None)
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, username=email)
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e
    user = db_user.get_tenant_entity_user_by_email(db, email)
    if not user:
        raise credentials_exception from None
    if user.tenant_id == 18 and iat is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from None
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough permissions") from None
    return user


def get_tenant_entity_user_2(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_pg_db),  # noqa
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    except ExpiredSignatureError:
        # The token was successfully *opened*, but is expired → 401
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTClaimsError:
        # The token was successfully *opened*, but has invalid claims or bad signature → 401
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token signature or claims.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (JWTError, ValidationError):
        # The token cannot even be parsed or is otherwise invalid → 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not open token (malformed JWT)"
        ) from None
    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not open token (missing sub)"
        ) from None

    user = db_user.get_tenant_entity_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found or unauthorized") from None
    iat = payload.get("iat", None)
    if user.tenant_id == 18 and iat is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from None
    token_scopes = payload.get("scopes", [])
    token_data = TokenData(scopes=token_scopes, username=email)
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough permissions") from None
    return user


def get_entity_user_for_attendance(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_pg_db),  # noqa
):
    # needs to be deleted later
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token is required",
        )

    # needs to be changed to 401 later
    credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
        email: str = payload.get("sub")
        if not email:
            raise credentials_exception from None
        iat = payload.get("iat", None)
        exp = payload.get("exp")
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, username=email)
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e
    if exp + attendance_token_extra_time < int(time.time()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expired") from None
    user = db_user.get_tenant_entity_user_by_email(db, email)
    if not user:
        raise credentials_exception from None
    if user.tenant_id == 18 and iat is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from None
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough permissions") from None
    return user


def get_entity_user_for_attendance_2(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_pg_db),  # noqa
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
    except ExpiredSignatureError:
        # The token was successfully *opened*, but is expired → 401
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except JWTClaimsError:
        # The token was successfully *opened*, but has invalid claims or bad signature → 401
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token signature or claims.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except (JWTError, ValidationError):
        # The token cannot even be parsed or is otherwise invalid → 400
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not open token (malformed JWT)"
        ) from None

    email: str = payload.get("sub")
    if not email:
        # If the token is well-formed but missing crucial data, decide how to handle
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Could not open token (missing sub)"
        ) from None

    user = db_user.get_tenant_entity_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found or unauthorized") from None
    iat = payload.get("iat", None)
    if user.tenant_id == 18 and iat is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from None
    token_scopes = payload.get("scopes", [])
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough permissions") from None
    return user


oauth2_scheme_sysadmin = OAuth2PasswordBearer(tokenUrl="system_token", scopes=scopes)


def get_current_sysadmin(token: str = Depends(oauth2_scheme_sysadmin)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception from None
        iat = payload.get("iat", None)
        if not iat:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from None
        token_scopes = payload.get("scopes", [])

        token_data = TokenData(scopes=token_scopes, username=username)
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e

    if username != SYSADMIN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not enough permissions") from None
    return token_data


oauth2_scheme_tenant = OAuth2PasswordBearer(tokenUrl="tenant_token", scopes=scopes)


def get_current_tenant_admin(token: str = Depends(oauth2_scheme_tenant), db: Session = Depends(get_pg_db)):  # noqa
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception from None
        iat = payload.get("iat", None)
        if not iat:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        token_scopes = payload.get("scopes", [])

        token_data = TokenData(scopes=token_scopes, username=username)  # noqa
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e

    user = db_tenant_admin.get_tenant_admin_by_email(db, username)
    if not user:
        raise credentials_exception from None
    return user


oauth2_scheme_third_party = OAuth2PasswordBearer(tokenUrl="third_party_token", scopes=scopes)


def get_current_third_party_token(token: str = Depends(oauth2_scheme_third_party), db: Session = Depends(get_pg_db)):  # noqa
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        iat = payload.get("iat", None)
        if not iat:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, username=username)  # noqa
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e

    user = db_third_party.get_third_party_by_username(db, username)
    if not user:
        raise credentials_exception from None
    return user


oauth2_scheme_relative = OAuth2PasswordBearer(tokenUrl="relative_token", scopes=scopes)


def get_current_relative(
    token: str = Depends(oauth2_scheme_relative),
    db: Session = Depends(get_pg_db),  # noqa: B008
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        iat = payload.get("iat", None)
        if not iat:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
        token_scopes = payload.get("scopes", [])
        token_data = TokenData(scopes=token_scopes, username=username)  # noqa
    except (JWTError, ValidationError) as e:
        raise credentials_exception from e

    relative = db_relative.get_relative_by_username(db, username)
    if not relative:
        raise credentials_exception from None
    return relative


def is_authenticated(token=Depends(security)):  # noqa
    try:
        jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    return True
