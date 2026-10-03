from typing import Annotated
from collections import deque
from math import ceil
from time import monotonic

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from auth.authentication import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    create_partner_access_token,
    M2M_ACCESS_TOKEN_EXPIRE_MINUTES,
    verify_password,
    verify_mfa,
)
from databases.partners import get_partner_client
from model.users import OAuthTokenResponse, SignInRequest, TokenResponse

auth_router = APIRouter(prefix="/auth", tags=["authentication"])
basic_auth = HTTPBasic(auto_error=False)
sign_in_attempts: dict[str, deque[float]] = {}


async def limit_sign_in(request: Request) -> None:
    now = monotonic()
    # Remove também clientes inativos para não acumular IPs indefinidamente.
    for client_ip, attempts in list(sign_in_attempts.items()):
        while attempts and now - attempts[0] >= 5:
            attempts.popleft()
        if not attempts:
            del sign_in_attempts[client_ip]

    client_ip = request.client.host if request.client else "unknown"
    attempts = sign_in_attempts.setdefault(client_ip, deque())
    if len(attempts) >= 2:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Try again later.",
            headers={"Retry-After": str(ceil(5 - (now - attempts[0])))},
        )
    attempts.append(now)


@auth_router.post(
    "/sign-in", response_model=TokenResponse, dependencies=[Depends(limit_sign_in)]
)
async def sign_in(credentials: SignInRequest) -> TokenResponse:
    user = authenticate_user(credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not verify_mfa(user, credentials.mfa_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing MFA code",
        )
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@auth_router.post("/token", response_model=OAuthTokenResponse)
async def issue_client_credentials_token(
    grant_type: Annotated[str, Form()],
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)],
    scope: Annotated[str | None, Form()] = None,
) -> OAuthTokenResponse:
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsupported_grant_type",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
            headers={"WWW-Authenticate": "Basic"},
        )

    client = get_partner_client(credentials.username)
    if client is None or not client.is_active or not verify_password(
        credentials.password, client.secret_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_client",
            headers={"WWW-Authenticate": "Basic"},
        )

    allowed_scopes = set(client.allowed_scopes.split())
    requested_scopes = set(scope.split()) if scope else allowed_scopes
    if not requested_scopes.issubset(allowed_scopes):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_scope",
        )
    granted_scope = " ".join(sorted(requested_scopes))
    return OAuthTokenResponse(
        access_token=create_partner_access_token(client.client_id, requested_scopes),
        expires_in=M2M_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        scope=granted_scope,
    )
