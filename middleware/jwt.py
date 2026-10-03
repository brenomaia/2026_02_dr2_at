import jwt
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from auth.authentication import decode_access_token
from databases.partners import get_partner_client
from databases.users import get_user_by_username
from model.users import CurrentPartner, CurrentUser, Role


PUBLIC_PATHS = {
    "/health", "/auth/sign-in", "/auth/token", "/openapi.json", "/docs", "/docs/oauth2-redirect"
}


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return self._unauthorized("Missing bearer token")

        token = authorization.removeprefix("Bearer ").strip()
        try:
            self._set_principal(request, decode_access_token(token))
        except (jwt.PyJWTError, ValueError, TypeError):
            return self._unauthorized("Invalid or expired token")
        return await call_next(request)

    @staticmethod
    def _set_principal(request: Request, payload: dict) -> None:
        principal_type = payload.get("principal_type")
        subject = payload.get("sub")
        scope = payload.get("scope")
        if not isinstance(subject, str) or not isinstance(scope, str):
            raise ValueError("Invalid token payload")

        if principal_type == "user":
            role = payload.get("role")
            if not isinstance(role, str) or scope:
                raise ValueError("Invalid user token")
            user_record = get_user_by_username(subject)
            if user_record is None or user_record.role != role:
                raise ValueError("Invalid user")
            request.state.current_user = CurrentUser(
                id=user_record.id, username=user_record.username, role=Role(role)
            )
            return

        if principal_type == "partner":
            client_id = payload.get("client_id")
            if client_id != subject or not isinstance(client_id, str) or "role" in payload:
                raise ValueError("Invalid partner token")
            client = get_partner_client(client_id)
            token_scopes = frozenset(scope.split())
            allowed_scopes = (
                frozenset(client.allowed_scopes.split())
                if client else frozenset()
            )
            if client is None or not client.is_active or not token_scopes.issubset(allowed_scopes):
                raise ValueError("Invalid partner")
            request.state.current_partner = CurrentPartner(client_id=client_id, scopes=token_scopes)
            return

        raise ValueError("Invalid principal type")

    @staticmethod
    def _unauthorized(detail: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": "Bearer"},
        )
