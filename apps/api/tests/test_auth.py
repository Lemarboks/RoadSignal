from fastapi.testclient import TestClient

from app.auth import MEMORY_REFRESH_SESSIONS, MEMORY_USERS
from app.main import app

client = TestClient(app)


def setup_function():
    MEMORY_USERS.clear()
    MEMORY_REFRESH_SESSIONS.clear()


def test_register_login_refresh_logout_flow():
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": "driver@example.com", "password": "Correct-Horse-2026", "name": "Test Driver"},
    )
    assert registration.status_code == 201
    tokens = registration.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["user"]["role"] == "driver"
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "driver@example.com", "password": "Correct-Horse-2026"},
    )
    assert login.status_code == 200
    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["refresh_token"] != login.json()["refresh_token"]
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": login.json()["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/logout", json={"refresh_token": refresh.json()["refresh_token"]}).status_code == 204


def test_duplicate_email_and_bad_password_are_rejected_without_leaking_hashes():
    payload = {"email": "driver@example.com", "password": "Correct-Horse-2026", "name": "Test Driver"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 409
    denied = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": "Incorrect-Password"})
    assert denied.status_code == 401
    assert "hash" not in denied.text.casefold()


def test_security_headers_and_protected_profile():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
