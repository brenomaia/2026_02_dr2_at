import hmac
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.openapi.models import OAuthFlowClientCredentials, OAuthFlows
from fastapi.security import OAuth2
from passlib.context import CryptContext

from config import get_settings
from databases.users import get_user_by_username
from model.users import CurrentPartner, CurrentUser, Role

settings = get_settings()
JWT_SECRET_KEY = settings.jwt_secret_key
JWT_ALGORITHM = settings.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes
M2M_ACCESS_TOKEN_EXPIRE_MINUTES = settings.m2m_access_token_expire_minutes
JWT_ISSUER = settings.jwt_issuer
JWT_AUDIENCE = settings.jwt_audience
SIMULATED_ADMIN_MFA_CODE = "123456"
PARTNER_CONSULTAS_READ_SCOPE = "partner:consultas:read"

oauth2_scheme = OAuth2(
    flows=OAuthFlows(
        clientCredentials=OAuthFlowClientCredentials(
            tokenUrl="/auth/token",
            scopes={
                PARTNER_CONSULTAS_READ_SCOPE: "Read partner-safe appointment summaries."
            },
        )
    ),
    scheme_name="OAuth2ClientCredentials",
)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(plain_password, password_hash)
    except (ValueError, TypeError):
        return False


def authenticate_user(username: str, password: str) -> CurrentUser | None:
    user_record = get_user_by_username(username)
    if user_record is None or not verify_password(password, user_record.password_hash):
        return None
    return CurrentUser(id=user_record.id, username=username, role=Role(user_record.role))


def verify_mfa(user: CurrentUser, mfa_code: str | None) -> bool:
    if user.role is not Role.ADMIN:
        return True
    return mfa_code is not None and hmac.compare_digest(mfa_code, SIMULATED_ADMIN_MFA_CODE)


def _token_payload(*, subject: str, principal_type: str, expires_in_minutes: int) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_in_minutes),
        "jti": str(uuid4()),
        "principal_type": principal_type,
    }


def create_access_token(user: CurrentUser) -> str:
    payload = _token_payload(
        subject=user.username,
        principal_type="user",
        expires_in_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    payload.update({"role": user.role.value, "scope": ""})
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_partner_access_token(client_id: str, scopes: set[str]) -> str:
    payload = _token_payload(
        subject=client_id,
        principal_type="partner",
        expires_in_minutes=M2M_ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    payload.update({"client_id": client_id, "scope": " ".join(sorted(scopes))})
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        audience=JWT_AUDIENCE,
        options={"require": ["iss", "aud", "sub", "iat", "exp", "jti", "principal_type", "scope"]},
    )


async def get_current_user(
    request: Request,
    _: Annotated[str, Depends(oauth2_scheme)],
) -> CurrentUser:
    current_user = getattr(request.state, "current_user", None)
    if not isinstance(current_user, CurrentUser):
        raise credentials_exception
    return current_user


async def get_current_partner(
    request: Request,
    _: Annotated[str, Depends(oauth2_scheme)],
) -> CurrentPartner:
    partner = getattr(request.state, "current_partner", None)
    if not isinstance(partner, CurrentPartner):
        raise credentials_exception
    return partner


def require_roles(*allowed_roles: Role):
    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return current_user

    return role_checker


def require_scopes(*required_scopes: str):
    async def scope_checker(
        partner: Annotated[CurrentPartner, Depends(get_current_partner)],
    ) -> CurrentPartner:
        if not set(required_scopes).issubset(partner.scopes):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return partner

    return scope_checker
