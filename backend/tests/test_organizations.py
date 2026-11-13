"""Each organization sees and uses only its own data."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import ORG_SUSPENDED, Organization, User
from tests.conftest import add_user, login_headers
from tests.test_capture import CAPTURED, fake_ifs, make_connection, make_target, public_url  # noqa: F401


def suspend(org_name: str) -> None:
    with SessionLocal() as db:
        org = db.scalar(select(Organization).where(Organization.name == org_name))
        org.status = ORG_SUSPENDED
        db.commit()


def test_migrations_match_the_models(client):
    # A model change without a migration would only show up on deploy.
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_seeded_admin_is_platform_admin_in_the_platform_org(client, auth_headers):
    me = client.get("/api/auth/me", headers=auth_headers).json()
    assert me["organization"]["name"] == "AtroNexus"
    assert me["role"] == "owner"
    assert me["is_platform_admin"] is True


def test_users_see_only_their_own_connections_and_targets(client, auth_headers, other_org_headers, fake_ifs):
    conn = make_connection(client, auth_headers)
    target = make_target(client, auth_headers, conn["id"])
    client.post(public_url(target), json=CAPTURED)

    assert client.get("/api/ifs-connections", headers=other_org_headers).json() == []
    assert client.get("/api/capture/targets", headers=other_org_headers).json() == []
    assert client.get("/api/capture/captures", headers=other_org_headers).json() == []
    assert client.get(
        "/api/capture/captures", params={"target_id": target["id"]}, headers=other_org_headers
    ).json() == []

    # The owner still sees everything.
    assert len(client.get("/api/capture/captures", headers=auth_headers).json()) == 1


def test_other_orgs_rows_answer_404(client, auth_headers, other_org_headers, fake_ifs):
    conn = make_connection(client, auth_headers)
    target = make_target(client, auth_headers, conn["id"])
    h = other_org_headers

    conn_body = {"name": "x", "base_url": "https://x.example.com", "auth_type": "basic", "username": "u", "secret": "p"}
    target_body = {"name": "x", "connection_id": conn["id"], "endpoint_path": "/x", "http_method": "POST",
                   "body_template": '{"a": "{ip}"}'}
    checks = [
        client.get(f"/api/ifs-connections/{conn['id']}", headers=h),
        client.put(f"/api/ifs-connections/{conn['id']}", json=conn_body, headers=h),
        client.post(f"/api/ifs-connections/{conn['id']}/test", headers=h),
        client.delete(f"/api/ifs-connections/{conn['id']}", headers=h),
        client.get(f"/api/capture/targets/{target['id']}", headers=h),
        client.put(f"/api/capture/targets/{target['id']}", json=target_body, headers=h),
        client.post(f"/api/capture/targets/{target['id']}/test", headers=h),
        client.delete(f"/api/capture/targets/{target['id']}", headers=h),
    ]
    assert [r.status_code for r in checks] == [404] * len(checks)
    # Nothing changed for the owner.
    assert client.get(f"/api/ifs-connections/{conn['id']}", headers=auth_headers).json()["name"] == conn["name"]
    assert client.get(f"/api/capture/targets/{target['id']}", headers=auth_headers).json()["name"] == target["name"]


def test_a_target_cant_use_another_orgs_connection(client, auth_headers, other_org_headers, fake_ifs):
    # That would write to the other customer's IFS with their service user.
    theirs = make_connection(client, auth_headers)
    body = {"name": "Sneaky", "connection_id": theirs["id"], "endpoint_path": "/x", "http_method": "POST",
            "body_template": '{"a": "{ip}"}'}
    res = client.post("/api/capture/targets", json=body, headers=other_org_headers)
    assert res.status_code == 422

    mine = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, mine["id"])
    res = client.put(f"/api/capture/targets/{target['id']}", json=body, headers=other_org_headers)
    assert res.status_code == 422


def test_new_rows_belong_to_the_creators_org(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    with SessionLocal() as db:
        bob = db.scalar(select(User).where(User.username == "bob"))
        from app.ifs.models import IfsConnection

        assert db.get(IfsConnection, conn["id"]).organization_id == bob.organization_id


def test_suspended_org_cant_sign_in_or_use_its_token(client, other_org_headers):
    suspend("Other Co")
    res = client.post("/api/auth/login", json={"username": "bob", "password": "pass1234"})
    assert res.status_code == 403
    assert "suspended" in res.json()["detail"]
    assert client.get("/api/auth/me", headers=other_org_headers).status_code == 403
    assert client.get("/api/ifs-connections", headers=other_org_headers).status_code == 403


def test_suspended_orgs_capture_links_stop_working(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    assert client.get(public_url(target)).status_code == 200
    suspend("Other Co")
    assert client.get(public_url(target)).status_code == 404
    assert client.post(public_url(target), json=CAPTURED).status_code == 404


def test_suspending_one_org_leaves_others_alone(client, auth_headers, other_org_headers):
    suspend("Other Co")
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 200


def test_users_of_the_same_org_share_its_data(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    add_user("carol", "Other Co", role="member")
    carol = login_headers(client, "carol", "pass1234")
    assert [c["id"] for c in client.get("/api/ifs-connections", headers=carol).json()] == [conn["id"]]


def test_a_database_from_before_migrations_is_upgraded_with_its_data(client):
    # Simulates the production database: tables made by create_all (= 0001),
    # data in them, and no version recorded (alembic_version empty or missing).
    from alembic import command
    from sqlalchemy import text

    from app import migrate
    from tests.conftest import reset_database

    reset_database()
    with engine.begin() as conn:
        command.upgrade(migrate._config(conn), "0001")
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(text(
            "INSERT INTO users (username, password_hash, is_active, created_at) "
            "VALUES ('old', 'h', :yes, CURRENT_TIMESTAMP)"
        ), {"yes": True})
        conn.execute(text(
            "INSERT INTO ifs_connections (name, base_url, auth_type, secret_enc, created_at, updated_at) "
            "VALUES ('Old IFS', 'https://x', 'basic', 'e', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))

    migrate.upgrade()
    migrate.upgrade()  # a second start changes nothing

    with SessionLocal() as db:
        [org] = db.scalars(select(Organization)).all()
        old = db.scalar(select(User).where(User.username == "old"))
        from app.ifs.models import IfsConnection

        [conn] = db.scalars(select(IfsConnection)).all()
        assert (org.name, old.organization_id, old.role, old.is_platform_admin) == ("AtroNexus", org.id, "owner", True)
        assert conn.organization_id == org.id
