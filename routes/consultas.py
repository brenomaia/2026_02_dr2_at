from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from auth.authentication import Role, get_current_user, require_roles
from database import get_session
from databases.consultas import (
    create_consulta as persist_consulta,
    delete_consulta as remove_consulta,
    get_consulta_by_id,
    list_consultas as fetch_consultas,
    update_consulta as persist_updated_consulta,
    update_doctor_notes,
)
from model.consultas import (
    Consulta,
    ConsultaCreate,
    ConsultaResponse,
    ConsultaUpdate,
    DoctorConsultaResponse,
    DoctorNotesResponse,
    DoctorNotesUpdate,
)
from model.users import CurrentUser

consultas_router = APIRouter(prefix="/consultas")
templates = Jinja2Templates(
    directory="./templates",
)


def _get_consulta_or_404(consulta_id: UUID, session: Session) -> Consulta:
    consulta = get_consulta_by_id(session, consulta_id)
    if consulta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return consulta


def _to_consulta_response(consulta: Consulta) -> ConsultaResponse:
    return ConsultaResponse(
        **consulta.model_dump(exclude={"audit", "doctor_notes"})
    )


def _to_doctor_consulta_response(consulta: Consulta) -> DoctorConsultaResponse:
    return DoctorConsultaResponse(**consulta.model_dump(exclude={"audit"}))


async def _get_consulta_owned_by_doctor(
    consulta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Consulta:
    consulta = _get_consulta_or_404(consulta_id, session)
    if current_user.role is not Role.DOCTOR or current_user.id != consulta.medico_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return consulta


async def _get_consulta_visible_to_current_user(
    consulta_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Consulta:
    consulta = _get_consulta_or_404(consulta_id, session)

    if current_user.role is Role.DOCTOR:
        if current_user.id != consulta.medico_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    elif current_user.role not in (Role.RECEPTIONIST, Role.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return consulta


@consultas_router.get(
    "", dependencies=[Depends(require_roles(Role.RECEPTIONIST, Role.ADMIN))]
)
async def list_consultas(
    request: Request, session: Annotated[Session, Depends(get_session)]
):
    consultas = [_to_consulta_response(consulta) for consulta in fetch_consultas(session)]
    return templates.TemplateResponse(
        request=request,
        name="consultas/list.html",
        context={"consultas": consultas},
    )


@consultas_router.post(
    "",
    response_model=ConsultaResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(Role.RECEPTIONIST))],
)
async def create_consulta(
    payload: ConsultaCreate, session: Annotated[Session, Depends(get_session)]
) -> ConsultaResponse:
    consulta = persist_consulta(session, payload)
    return _to_consulta_response(consulta)


@consultas_router.get(
    "/{consulta_id}",
    response_model=ConsultaResponse | DoctorConsultaResponse,
)
async def get_consulta(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    consulta: Annotated[Consulta, Depends(_get_consulta_visible_to_current_user)],
) -> ConsultaResponse | DoctorConsultaResponse:
    if current_user.role is Role.DOCTOR:
        return _to_doctor_consulta_response(consulta)
    return _to_consulta_response(consulta)


@consultas_router.put(
    "/{consulta_id}",
    response_model=ConsultaResponse,
    dependencies=[Depends(require_roles(Role.RECEPTIONIST))],
)
async def update_consulta(
    consulta_id: UUID,
    payload: ConsultaUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> ConsultaResponse:
    consulta = _get_consulta_or_404(consulta_id, session)
    consulta = persist_updated_consulta(session, consulta, payload)
    return _to_consulta_response(consulta)


@consultas_router.patch(
    "/{consulta_id}/doctor-notes",
    response_model=DoctorNotesResponse,
    dependencies=[Depends(require_roles(Role.DOCTOR))],
)
async def add_doctor_notes(
    payload: DoctorNotesUpdate,
    consulta: Annotated[Consulta, Depends(_get_consulta_owned_by_doctor)],
    session: Annotated[Session, Depends(get_session)],
) -> DoctorNotesResponse:
    consulta = update_doctor_notes(session, consulta, payload.doctor_notes)
    return DoctorNotesResponse(
        id=consulta.id,
        doctor_notes=consulta.doctor_notes,
        updated_at=consulta.updated_at,
    )


@consultas_router.delete(
    "/{consulta_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(Role.RECEPTIONIST))],
)
async def delete_consulta(
    consulta_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> None:
    consulta = _get_consulta_or_404(consulta_id, session)
    remove_consulta(session, consulta)
