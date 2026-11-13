import pytest

from app.config import get_settings
from app.db import normalize_database_url

KEY = "k" * 40


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "internal_api_key", KEY)


def test_without_key_configured_everything_works_as_before(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).status_code == 200


def test_requests_without_the_key_are_refused(client, with_key):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 403
    assert client.get("/api/public/capture/x/REQ-1").status_code == 403
    assert client.get("/docs").status_code == 403


def test_wrong_key_is_refused(client, with_key):
    res = client.get("/api/public/capture/x/REQ-1", headers={"X-Internal-Key": "nope"})
    assert res.status_code == 403


def test_right_key_is_let_through(client, with_key):
    res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        headers={"X-Internal-Key": KEY},
    )
    assert res.status_code == 200


def test_health_check_needs_no_key(client, with_key):
    assert client.get("/api/health").status_code == 200


def test_postgres_urls_get_the_psycopg_driver():
    assert normalize_database_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    assert normalize_database_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_database_url("sqlite:///./x.db") == "sqlite:///./x.db"
