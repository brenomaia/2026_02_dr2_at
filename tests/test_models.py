from uuid import uuid4

import pytest
from pydantic import ValidationError

from model.consultas import ConsultaCreate, DoctorNotesUpdate
from model.users import SignInRequest


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            SignInRequest,
            {"username": "doctor", "password": "password", "role": "admin"},
        ),
        (
            DoctorNotesUpdate,
            {"doctor_notes": "Patient stable.", "audit": "unexpected"},
        ),
        (
            ConsultaCreate,
            {
                "paciente_id": str(uuid4()),
                "medico_id": str(uuid4()),
                "creator_id": str(uuid4()),
                "scheduled_at": "2026-10-01T10:00:00Z",
                "doctor_notes": "unexpected",
            },
        ),
    ],
)
def test_models_reject_undeclared_fields(model, payload):
    with pytest.raises(ValidationError, match="extra_forbidden"):
        model(**payload)
