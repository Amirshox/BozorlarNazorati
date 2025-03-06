from jose import JWTError, jwt
from starlette.authentication import AuthenticationBackend

from config import ALGORITHM, SECRET_KEY


class JWTAuthBackend(AuthenticationBackend):
    async def authenticate(self, request):
        authorization = request.headers.get("Authorization")
        try:
            scheme, token = authorization.split()
        except (ValueError, AttributeError):
            return False, None
        if scheme.lower() != "bearer":
            return False, None
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], options={"verify_exp": False})
            username: str = payload.get("sub")
            return True, username
        except JWTError:
            return False, None
