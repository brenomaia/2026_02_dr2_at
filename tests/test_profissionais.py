import pytest
from fastapi.testclient import TestClient

from auth.authentication import create_access_token
from main import app
from model.users import CurrentUser, Role

client = TestClient(app)


@pytest.mark.parametrize(
    ("username", "role"),
    [("doctor", Role.DOCTOR), ("receptionist", Role.RECEPTIONIST)],
)
def test_non_admin_cannot_create_receptionist(username: str, role: Role):
    token = create_access_token(CurrentUser(username=username, role=role))

    response = client.post(
        "/profissionais/receptionists",
        json={"username": "new_receptionist", "password": "secure-password"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_create_receptionist_requires_a_bearer_token():
    response = client.post(
        "/profissionais/receptionists",
        json={"username": "new_receptionist", "password": "secure-password"},
    )

    assert response.status_code == 401
