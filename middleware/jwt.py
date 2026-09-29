import jwt
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import UUID

from auth.authentication import JWT_ALGORITHM, JWT_SECRET_KEY
from databases.users import get_user_by_username
from model.users import CurrentUser, Role


PUBLIC_PATHS = {"/health", "/auth/sign-in", "/openapi.json"}


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return self._unauthorized("Missing bearer token")

        token = authorization.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
            )
            username = payload.get("sub")
            role = payload.get("role")
            if not isinstance(username, str) or not isinstance(role, str):
                raise ValueError("Invalid token payload")

            user_record = get_user_by_username(username)
            if user_record is None:
                raise ValueError("Invalid user")
            if user_record.role != role:
                raise ValueError("Invalid user")

            request.state.current_user = CurrentUser(
                id=user_record.id,
                username=username,
                role=Role(role),
            )
        except (jwt.PyJWTError, ValueError):
            return self._unauthorized("Invalid or expired token")

        return await call_next(request)

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )
