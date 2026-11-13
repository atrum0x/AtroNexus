import os

os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123"
# SQLite by default. To run against Postgres:
#   TEST_DATABASE_URL=postgresql://user:pass@host/db uv run pytest
# (the tests drop and recreate every table, so never point it at real data)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test.db")
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["ENCRYPTION_KEY"] = "pXoiNs7zDJ7z0Xk1Ksj0uHnU7pVYxCw8H9C0y2Hx0wM="

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)


@pytest.fixture
def auth_headers(client):
    res = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}
