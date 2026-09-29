from fastapi import APIRouter, HTTPException, status

from auth.authentication import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
)
from model.users import SignInRequest, TokenResponse

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


@auth_router.post("/sign-in", response_model=TokenResponse)
async def sign_in(credentials: SignInRequest) -> TokenResponse:
    user = authenticate_user(credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
