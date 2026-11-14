import os

os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123"
# SQLite by default. To run against Postgres:
#   TEST_DATABASE_URL=postgresql://user:pass@host/db uv run pytest
# (the tests drop and recreate every table, so never point it at real data)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test.db")
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ENCRYPTION_KEY"] = "pXoiNs7zDJ7z0Xk1Ksj0uHnU7pVYxCw8H9C0y2Hx0wM="

from datetime import datetime, timezone  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models_registry  # noqa: E402, F401
from app.accounts import get_or_create_org  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.email.sender import outbox  # noqa: E402
from app.ifs import netguard  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.tools.service import set_enabled  # noqa: E402


# Tests don't use real DNS: every host resolves to a public address unless a
# test maps it (see tests/test_netguard.py).
FAKE_DNS: dict[str, list[str]] = {}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch):
    FAKE_DNS.clear()
    monkeypatch.setattr(netguard, "resolve", lambda host, port: FAKE_DNS.get(host, ["93.184.216.34"]))
    yield FAKE_DNS
    FAKE_DNS.clear()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from app.approvals.router import LIMITERS as APPROVAL_LIMITERS
    from app.capture.router import LIMITERS
    from app.messaging.router import hook_limiter as messaging_limiter

    for limiter in (*LIMITERS, *APPROVAL_LIMITERS, messaging_limiter):
        limiter.reset()
    yield


@pytest.fixture(autouse=True)
def clear_outbox():
    outbox.clear()
    yield
    outbox.clear()


def reset_database() -> None:
    # Alembic's own table isn't in the models, so drop it too; otherwise the
    # next start would think the (now empty) database is already up to date.
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.fixture
def client():
    # Starting the app runs the migrations and seeds the admin, like production.
    reset_database()
    with TestClient(app) as c:
        yield c
    reset_database()


def login_headers(client, username: str, password: str) -> dict[str, str]:
    res = client.post("/api/auth/login", json={"email": username, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    return login_headers(client, "admin", "admin123")


def add_user(username: str, org_name: str, password: str = "pass1234", **fields) -> None:
    fields.setdefault("email_verified_at", datetime.now(timezone.utc))
    with SessionLocal() as db:
        org = get_or_create_org(db, org_name)
        # Test organizations use the capture page; tool tests switch it off themselves.
        set_enabled(db, org.id, "capture", True, None)
        db.add(User(organization=org, username=username, password_hash=hash_password(password), **fields))
        db.commit()


@pytest.fixture
def other_org_headers(client):
    """Signed in as the owner of a second, unrelated customer organization."""
    add_user("bob", "Other Co", role="owner")
    return login_headers(client, "bob", "pass1234")
