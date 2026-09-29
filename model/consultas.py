from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import Field
from sqlmodel import Field as SQLField, SQLModel

from model.base import StrictModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Consulta(SQLModel, table=True):
    """Representação persistida de uma consulta."""

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    paciente_id: UUID = SQLField(index=True)
    medico_id: UUID = SQLField(index=True)
    created_at: datetime = SQLField(default_factory=utc_now)
    updated_at: datetime = SQLField(default_factory=utc_now)
    scheduled_at: datetime
    creator_id: UUID = SQLField(index=True)
    audit: str = ""
    doctor_notes: str = ""


class ConsultaResponse(StrictModel):
    """Dados de consulta seguros para exposição pela API."""

    id: UUID
    paciente_id: UUID
    medico_id: UUID
    created_at: datetime
    updated_at: datetime
    scheduled_at: datetime
    creator_id: UUID


class DoctorConsultaResponse(ConsultaResponse):
    """Consulta response for the doctor responsible for the appointment."""

    doctor_notes: str


class ConsultaCreate(StrictModel):
    paciente_id: UUID
    medico_id: UUID
    scheduled_at: datetime
    creator_id: UUID


class ConsultaUpdate(StrictModel):
    paciente_id: UUID | None = None
    medico_id: UUID | None = None
    scheduled_at: datetime | None = None
    creator_id: UUID | None = None


class DoctorNotesUpdate(StrictModel):
    doctor_notes: str


class DoctorNotesResponse(StrictModel):
    id: UUID
    doctor_notes: str
    updated_at: datetime
