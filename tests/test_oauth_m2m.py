import base64
from datetime import datetime, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from auth.authentication import JWT_ALGORITHM, JWT_SECRET_KEY, create_partner_access_token, hash_password
from database import create_db_and_tables, engine
from databases.partners import create_partner_client, get_partner_client
from main import app
from model.consultas import Consulta


def basic_auth(client_id: str, secret: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


@pytest.fixture
def partner_client():
    create_db_and_tables()
    client_id = f"partner-{uuid4()}"
    secret = "partner-secret"
    with Session(engine) as session:
        client = create_partner_client(
            session,
            client_id=client_id,
            secret_hash=hash_password(secret),
            allowed_scopes="partner:consultas:read",
        )
    assert client is not None
    return client_id, secret


def obtain_token(client: TestClient, client_id: str, secret: str, scope: str | None = None):
    data = {"grant_type": "client_credentials"}
    if scope is not None:
        data["scope"] = scope
    return client.post("/auth/token", data=data, headers=basic_auth(client_id, secret))


def test_client_credentials_issues_scoped_partner_token(partner_client):
    client_id, secret = partner_client
    with TestClient(app) as client:
        response = obtain_token(client, client_id, secret, "partner:consultas:read")

    assert response.status_code == 200
    body = response.json()
    payload = jwt.decode(
        body["access_token"],
        JWT_SECRET_KEY,
        algorithms=[JWT_ALGORITHM],
        audience="clinic-api",
        issuer="clinic-api",
    )
    assert body["token_type"] == "bearer"
    assert body["scope"] == "partner:consultas:read"
    assert body["expires_in"] == 900
    assert payload["principal_type"] == "partner"
    assert payload["sub"] == client_id
    assert payload["client_id"] == client_id
    assert payload["scope"] == "partner:consultas:read"
    assert "role" not in payload


@pytest.mark.parametrize(
    ("grant_type", "scope", "expected_detail"),
    [
        ("password", None, "unsupported_grant_type"),
        ("client_credentials", "partner:consultas:write", "invalid_scope"),
    ],
)
def test_client_credentials_rejects_invalid_grant_or_scope(
    partner_client, grant_type, scope, expected_detail
):
    client_id, secret = partner_client
    data = {"grant_type": grant_type}
    if scope:
        data["scope"] = scope
    with TestClient(app) as client:
        response = client.post("/auth/token", data=data, headers=basic_auth(client_id, secret))
    assert response.status_code == 400
    assert response.json()["detail"] == expected_detail


def test_client_credentials_rejects_invalid_secret(partner_client):
    client_id, _ = partner_client
    with TestClient(app) as client:
        response = obtain_token(client, client_id, "wrong-secret")
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_client"
    assert response.headers["www-authenticate"] == "Basic"


def test_partner_can_read_json_api_but_not_internal_or_mutating_routes(partner_client):
    client_id, secret = partner_client
    consulta = Consulta(
        paciente_id=uuid4(), medico_id=uuid4(), creator_id=uuid4(),
        scheduled_at=datetime(2026, 10, 1, 10, tzinfo=timezone.utc),
        doctor_notes="Confidential note.", audit="private audit",
    )
    with Session(engine) as session:
        session.add(consulta)
        session.commit()
        consulta_id = consulta.id

    with TestClient(app) as client:
        token_response = obtain_token(client, client_id, secret)
        headers = {"Authorization": f"Bearer {token_response.json()['access_token']}"}
        list_response = client.get("/api/consultas", headers=headers)
        detail_response = client.get(f"/api/consultas/{consulta_id}", headers=headers)
        internal_response = client.get("/consultas", headers=headers)
        mutate_response = client.patch(
            f"/consultas/{consulta_id}/doctor-notes",
            headers=headers,
            json={"doctor_notes": "Attempted change"},
        )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == str(consulta_id)
    assert "doctor_notes" not in detail_response.json()
    assert "audit" not in detail_response.json()
    assert internal_response.status_code == 401
    assert mutate_response.status_code == 401


def test_disabled_partner_cannot_use_already_issued_token(partner_client):
    client_id, secret = partner_client
    with TestClient(app) as client:
        token_response = obtain_token(client, client_id, secret)
        token = token_response.json()["access_token"]
        with Session(engine) as session:
            partner = get_partner_client(client_id, session)
            assert partner is not None
            partner.is_active = False
            session.add(partner)
            session.commit()
        response = client.get("/api/consultas", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_legacy_token_without_required_claims_is_rejected():
    legacy_token = jwt.encode(
        {"sub": "doctor", "role": "doctor"}, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM
    )
    with TestClient(app) as client:
        response = client.get("/consultas", headers={"Authorization": f"Bearer {legacy_token}"})
    assert response.status_code == 401


def test_openapi_advertises_client_credentials_flow():
    scheme = app.openapi()["components"]["securitySchemes"]["OAuth2ClientCredentials"]
    assert scheme["flows"]["clientCredentials"] == {
        "tokenUrl": "/auth/token",
        "scopes": {"partner:consultas:read": "Read partner-safe appointment summaries."},
    }
