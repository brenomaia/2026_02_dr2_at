from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field
from sqlmodel import Field as SQLField, SQLModel

from model.base import StrictModel


class Role(str, Enum):
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"
    ADMIN = "admin"


class User(SQLModel, table=True):
    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    username: str = SQLField(index=True, unique=True)
    password_hash: str
    role: str


class PartnerClient(SQLModel, table=True):
    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    client_id: str = SQLField(index=True, unique=True)
    secret_hash: str
    allowed_scopes: str = ""
    is_active: bool = True


def initial_users() -> list[User]:
    return [
        User(id=UUID("9416D005-00A3-4D30-8F7A-3016C89F1477"), username="receptionist", password_hash="$2b$12$Qy4wOgc.OO8NPplUkPGnjO.AqCYJM4.6rrarUo5Mp6xS3Kp6QvVsO", role=Role.RECEPTIONIST.value),
        User(id=UUID("B84A5BB7-2A0F-40F5-8A68-ACC7C4F8501D"), username="doctor", password_hash="$2b$12$EDUCEFR50l1Se6HUxETCk.NKZCGfgLnQ3znJg0EzACFnSRJ1Hz/Ai", role=Role.DOCTOR.value),
        User(
            id=UUID("DF7C9CBB-B647-4EA1-8538-6A585B747FB1"),
            username="admin",
            password_hash="$2b$12$36FzrfX5bgswCxrpsZtkv.m97IKKyzaMptk7EcAYdE2HC1FnQw9k.",
            role=Role.ADMIN.value,
        ),
    ]


class CurrentUser(StrictModel):
    id: UUID | None = None
    username: str
    role: Role


class CurrentPartner(StrictModel):
    client_id: str
    scopes: frozenset[str]


class SignInRequest(StrictModel):
    username: str
    password: str
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class TokenResponse(StrictModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class OAuthTokenResponse(TokenResponse):
    scope: str


class ReceptionistCreate(StrictModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class ReceptionistResponse(StrictModel):
    username: str
    role: Role
