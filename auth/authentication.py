from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

from databases.users import get_user_by_username
from model.users import CurrentUser, Role
from config import get_settings

settings = get_settings()
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/sign-in")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(plain_password, password_hash)
    except (ValueError, TypeError):
        return False


def authenticate_user(username: str, password: str) -> CurrentUser | None:
    user_record = get_user_by_username(username)
    if user_record is None:
        return None

    if not verify_password(password, user_record.password_hash):
        return None
    return CurrentUser(id=user_record.id, username=username, role=Role(user_record.role))


def create_access_token(user: CurrentUser) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": user.username, "role": user.role.value, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


async def get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> CurrentUser:
    current_user = getattr(request.state, "current_user", None)
    if not isinstance(current_user, CurrentUser):
        raise credentials_exception
    return current_user


def require_roles(*allowed_roles: Role):
    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,)
        return current_user

    return role_checker
