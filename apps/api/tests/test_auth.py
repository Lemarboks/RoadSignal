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
    assert "refresh_token" not in login.json()
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=strict" in login.headers["set-cookie"]
    refresh = client.post("/api/v1/auth/refresh", json={})
    assert refresh.status_code == 200
    assert "refresh_token" not in refresh.json()
    assert client.post("/api/v1/auth/logout", json={}).status_code == 204

def test_mobile_refresh_tokens_require_explicit_client_header():
    headers = {"X-RoadSignal-Client": "mobile"}
    registration = client.post("/api/v1/auth/register", headers=headers, json={"email":"mobile@example.com","password":"Correct-Horse-2026","name":"Mobile Driver"})
    token = registration.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", headers=headers, json={"refresh_token": token})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != token

def test_unknown_fields_and_uploads_are_rejected():
    bad = client.post("/api/v1/auth/login", json={"email":"driver@example.com","password":"Correct-Horse-2026","role":"administrator"})
    assert bad.status_code == 422
    upload = client.post("/api/v1/incidents", files={"file": ("report.txt", b"content")})
    assert upload.status_code == 415
    bot = client.post("/api/v1/auth/login", json={"email":"driver@example.com","password":"Correct-Horse-2026","website":"spam.example"})
    assert bot.status_code == 422


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
    assert response.headers["content-security-policy"].startswith("default-src 'none'")
