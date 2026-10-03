from fastapi.testclient import TestClient

from main import app
from routes import auth


def test_sign_in_limits_attempts_and_allows_retry_after_five_seconds(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(auth, "monotonic", lambda: now[0])
    monkeypatch.setattr(auth, "authenticate_user", lambda *_: None)
    client = TestClient(app)
    payload = {"username": "invalid", "password": "invalid"}

    assert client.post("/auth/sign-in", json=payload).status_code == 401
    assert client.post("/auth/sign-in", json=payload).status_code == 401
    response = client.post("/auth/sign-in", json=payload)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "5"
    now[0] = 104.9
    assert client.post("/auth/sign-in", json=payload).status_code == 429
    now[0] = 105.0
    assert client.post("/auth/sign-in", json=payload).status_code == 401


def test_sign_in_limit_is_per_client_ip(monkeypatch):
    monkeypatch.setattr(auth, "authenticate_user", lambda *_: None)
    first = TestClient(app, client=("192.0.2.1", 50000))
    second = TestClient(app, client=("192.0.2.2", 50000))
    payload = {"username": "invalid", "password": "invalid"}

    assert first.post("/auth/sign-in", json=payload).status_code == 401
    assert first.post("/auth/sign-in", json=payload).status_code == 401
    assert first.post("/auth/sign-in", json=payload).status_code == 429
    assert second.post("/auth/sign-in", json=payload).status_code == 401
    assert first.get("/health").status_code == 200
