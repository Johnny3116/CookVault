"""The optional password gate.

Setting COOKVAULT_PASSWORD used to brick the app outright, so these cover both
that it works and that the old scheme's cookies no longer do.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.auth import COOKIE_NAME
from app.main import app
from tests.conftest import TEST_PASSWORD


def test_gate_is_off_by_default(client):
    assert client.get("/auth/status").json() == {"auth_required": False}
    assert client.get("/recipes").status_code == 200


def test_health_stays_open_when_gated(locked_client):
    """/health is deliberately outside the gate so it works as a liveness probe."""
    assert locked_client.get("/health").status_code == 200


def test_gated_endpoints_refuse_anonymous_callers(locked_client):
    assert locked_client.get("/auth/status").json() == {"auth_required": True}
    assert locked_client.get("/recipes").status_code == 401
    assert locked_client.post("/recipes", json={"title": "x"}).status_code == 401


def test_wrong_password_is_rejected(locked_client):
    assert locked_client.post("/auth/login", json={"password": "wrong"}).status_code == 401
    assert locked_client.get("/recipes").status_code == 401


def test_login_issues_a_signed_token_that_is_not_the_password(locked_client):
    response = locked_client.post("/auth/login", json={"password": TEST_PASSWORD})

    assert response.status_code == 200
    cookie = response.cookies.get(COOKIE_NAME)
    assert cookie and "." in cookie
    assert TEST_PASSWORD not in cookie


def test_authenticated_requests_are_allowed(locked_client):
    locked_client.post("/auth/login", json={"password": TEST_PASSWORD})

    assert locked_client.get("/recipes").status_code == 200


def test_forged_and_legacy_cookies_are_rejected(locked_client):
    other = TestClient(app)

    for forged in ("9999999999.deadbeef", "not-a-token", "", TEST_PASSWORD):
        other.cookies.set(COOKIE_NAME, forged)
        assert other.get("/recipes").status_code == 401, f"accepted forged cookie {forged!r}"


def test_expired_tokens_are_rejected(locked_client, monkeypatch):
    import app.auth as auth

    locked_client.post("/auth/login", json={"password": TEST_PASSWORD})
    assert locked_client.get("/recipes").status_code == 200

    # Jump past the token's lifetime.
    real_time = auth.time.time
    monkeypatch.setattr(auth.time, "time", lambda: real_time() + auth.MAX_AGE_SECONDS + 60)

    assert locked_client.get("/recipes").status_code == 401


def test_logout_clears_the_session(locked_client):
    locked_client.post("/auth/login", json={"password": TEST_PASSWORD})

    assert locked_client.post("/auth/logout").status_code == 200
    assert TestClient(app).get("/recipes").status_code == 401
