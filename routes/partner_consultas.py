from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from auth.authentication import PARTNER_CONSULTAS_READ_SCOPE, require_scopes
from database import get_session
from databases.consultas import get_consulta_by_id, list_consultas
from model.consultas import Consulta, ConsultaResponse


partner_consultas_router = APIRouter(
    prefix="/api/consultas",
    tags=["partner consultations"],
    dependencies=[Depends(require_scopes(PARTNER_CONSULTAS_READ_SCOPE))],
)


def _to_partner_response(consulta: Consulta) -> ConsultaResponse:
    return ConsultaResponse(**consulta.model_dump(exclude={"audit", "doctor_notes"}))


@partner_consultas_router.get("", response_model=list[ConsultaResponse])
async def list_partner_consultas(
    session: Annotated[Session, Depends(get_session)],
) -> list[ConsultaResponse]:
    return [_to_partner_response(consulta) for consulta in list_consultas(session)]


@partner_consultas_router.get("/{consulta_id}", response_model=ConsultaResponse)
async def get_partner_consulta(
    consulta_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ConsultaResponse:
    consulta = get_consulta_by_id(session, consulta_id)
    if consulta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return _to_partner_response(consulta)
