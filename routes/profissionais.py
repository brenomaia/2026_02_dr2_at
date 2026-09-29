from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from auth.authentication import Role, hash_password, require_roles
from database import get_session
from databases.users import create_user
from model.users import ReceptionistCreate, ReceptionistResponse

profissionais_router = APIRouter(prefix="/profissionais", tags=["professionals"])


@profissionais_router.post(
    "/receptionists",
    response_model=ReceptionistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_receptionist(
    payload: ReceptionistCreate,
    _: Annotated[object, Depends(require_roles(Role.ADMIN))],
    session: Annotated[Session, Depends(get_session)],
) -> ReceptionistResponse:
    user = create_user(
        session,
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=Role.RECEPTIONIST.value,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    return ReceptionistResponse(
        username=payload.username,
        role=Role.RECEPTIONIST,
    )
