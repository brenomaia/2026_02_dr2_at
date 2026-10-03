from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from auth.authentication import create_access_token, get_current_user
from database import create_db_and_tables, engine, get_session
from databases.users import get_user_by_username
from main import app
from model.consultas import Consulta, ConsultaCreate, ConsultaResponse
from model.users import CurrentUser, Role
from routes.consultas import create_consulta

@pytest.fixture(autouse=True)
def clear_consultas_table():
    create_db_and_tables()
    from sqlmodel import Session, delete

    with Session(engine) as session:
        session.exec(delete(Consulta))
        session.commit()
    yield
    with Session(engine) as session:
        session.exec(delete(Consulta))
        session.commit()


def test_create_consulta_persists_consulta_in_database():
    payload = ConsultaCreate(
        paciente_id=uuid4(),
        medico_id=uuid4(),
        scheduled_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
        creator_id=uuid4(),
    )

    with TestClient(app) as client:
        token = create_access_token(CurrentUser(username="receptionist", role=Role.RECEPTIONIST))
        response = client.post("/consultas", json=payload.model_dump(mode="json"), headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201
    consulta_response = ConsultaResponse(**response.json())

    from sqlmodel import Session
    with Session(engine) as session:
        consulta = session.get(Consulta, consulta_response.id)

    assert consulta is not None
    assert consulta.paciente_id == payload.paciente_id
    assert consulta.medico_id == payload.medico_id
    assert consulta.scheduled_at == payload.scheduled_at
    assert consulta.creator_id == payload.creator_id
    assert consulta.audit == ""
    assert consulta.doctor_notes == ""
    assert "audit" not in consulta_response.model_dump()
    assert "doctor_notes" not in consulta_response.model_dump()
    assert isinstance(consulta_response, ConsultaResponse)


def test_doctor_can_add_notes_only_to_their_own_consulta():
    doctor = get_user_by_username("doctor")
    assert doctor is not None

    owned_consulta = Consulta(
        paciente_id=uuid4(),
        medico_id=doctor.id,
        scheduled_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
        creator_id=uuid4(),
    )
    other_consulta = Consulta(
        paciente_id=uuid4(),
        medico_id=uuid4(),
        scheduled_at=datetime(2026, 10, 1, 11, tzinfo=timezone.utc),
        creator_id=uuid4(),
    )
    from sqlmodel import Session
    with Session(engine) as session:
        session.add(owned_consulta)
        session.add(other_consulta)
        session.commit()
        owned_consulta_id = owned_consulta.id
        other_consulta_id = other_consulta.id

    token = create_access_token(CurrentUser(username="doctor", role=Role.DOCTOR))
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        owned_response = client.patch(f"/consultas/{owned_consulta_id}/doctor-notes", json={"doctor_notes": "Patient stable."}, headers=headers)
        other_response = client.patch(f"/consultas/{other_consulta_id}/doctor-notes", json={"doctor_notes": "Patient stable."}, headers=headers)
        owned_get_response = client.get(f"/consultas/{owned_consulta_id}", headers=headers)
        other_get_response = client.get(f"/consultas/{other_consulta_id}", headers=headers)

    assert owned_response.status_code == 200
    with Session(engine) as session:
        saved_owned = session.get(Consulta, owned_consulta_id)
        saved_other = session.get(Consulta, other_consulta_id)
    assert saved_owned is not None and saved_owned.doctor_notes == "Patient stable."
    assert other_response.status_code == 403
    assert saved_other is not None and saved_other.doctor_notes == ""
    assert owned_get_response.status_code == 200
    assert owned_get_response.json()["doctor_notes"] == "Patient stable."
    assert "audit" not in owned_get_response.json()
    assert other_get_response.status_code == 403


def test_doctor_can_only_view_notes_from_their_own_consultas():
    doctor = get_user_by_username("doctor")
    assert doctor is not None

    own_consulta = Consulta(
        paciente_id=uuid4(),
        medico_id=doctor.id,
        scheduled_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
        creator_id=uuid4(),
        doctor_notes="Own patient note.",
    )
    another_doctors_consulta = Consulta(
        paciente_id=uuid4(),
        medico_id=uuid4(),
        scheduled_at=datetime(2026, 10, 1, 11, tzinfo=timezone.utc),
        creator_id=uuid4(),
        doctor_notes="Confidential note.",
    )
    from sqlmodel import Session
    with Session(engine) as session:
        session.add(own_consulta)
        session.add(another_doctors_consulta)
        session.commit()
        own_consulta_id = own_consulta.id
        another_doctors_consulta_id = another_doctors_consulta.id

    token = create_access_token(CurrentUser(username="doctor", role=Role.DOCTOR))
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        own_response = client.get(f"/consultas/{own_consulta_id}", headers=headers)
        other_response = client.get(
            f"/consultas/{another_doctors_consulta_id}", headers=headers
        )

    assert own_response.status_code == 200
    assert own_response.json()["doctor_notes"] == "Own patient note."
    assert other_response.status_code == 403


def test_update_consulta_cannot_update_doctor_notes():
    consulta = Consulta(
        paciente_id=uuid4(),
        medico_id=uuid4(),
        scheduled_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
        creator_id=uuid4(),
        doctor_notes="Original note.",
    )
    from sqlmodel import Session
    with Session(engine) as session:
        session.add(consulta)
        session.commit()
        consulta_id = consulta.id

    token = create_access_token(
        CurrentUser(username="receptionist", role=Role.RECEPTIONIST)
    )
    with TestClient(app) as client:
        response = client.put(
            f"/consultas/{consulta_id}",
            json={"doctor_notes": "Tampered note."},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 422
    with Session(engine) as session:
        saved_consulta = session.get(Consulta, consulta_id)
    assert saved_consulta is not None
    assert saved_consulta.doctor_notes == "Original note."


def test_doctor_cannot_delete_even_their_own_consulta():
    doctor = get_user_by_username("doctor")
    assert doctor is not None

    consulta = Consulta(
        paciente_id=uuid4(),
        medico_id=doctor.id,
        scheduled_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
        creator_id=uuid4(),
    )
    from sqlmodel import Session
    with Session(engine) as session:
        session.add(consulta)
        session.commit()
        consulta_id = consulta.id

    token = create_access_token(CurrentUser(username="doctor", role=Role.DOCTOR))
    with TestClient(app) as client:
        response = client.delete(
            f"/consultas/{consulta_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    with Session(engine) as session:
        assert session.get(Consulta, consulta_id) is not None


def test_doctor_cannot_delete_even_their_own_consulta_with_mocked_auth_and_db():
    consulta_id = uuid4()
    mocked_session = MagicMock()
    doctor = CurrentUser(id=uuid4(), username="doctor", role=Role.DOCTOR)

    def override_session():
        yield mocked_session

    app.dependency_overrides[get_current_user] = lambda: doctor
    app.dependency_overrides[get_session] = override_session
    token = create_access_token(doctor)

    # A camada JWT ainda exige que o token corresponda a um usuário. Este mock
    # evita consultar o banco durante a autenticação do request.
    mocked_user_record = MagicMock(
        username=doctor.username,
        role=doctor.role.value,
        id=doctor.id,
    )
    try:
        with patch(
            "middleware.jwt.get_user_by_username", return_value=mocked_user_record
        ):
            with TestClient(app) as client:
                response = client.delete(
                    f"/consultas/{consulta_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    mocked_session.get.assert_not_called()
    mocked_session.delete.assert_not_called()
    mocked_session.commit.assert_not_called()

