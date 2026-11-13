"""Sign-up, email sign-in, email verification and password reset."""

import re
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select, update

from app.accounts import seed_platform_admin
from app.config import get_settings
from app.db import SessionLocal
from app.email.sender import outbox
from app.models import AuthToken, User
from tests.conftest import login_headers

SIGNUP = {
    "organization_name": "Acme Ltd",
    "name": "Ann Owner",
    "email": "Ann@Acme.example",
    "password": "correct horse",
}
CONNECTION = {
    "name": "Acme IFS",
    "base_url": "https://ifs.acme.example",
    "auth_type": "basic",
    "username": "svc",
    "secret": "pw",
}


def signup(client, **overrides):
    return client.post("/api/auth/signup", json={**SIGNUP, **overrides})


def bearer(res) -> dict[str, str]:
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def link_token(path: str) -> str:
    """The token from the newest email whose link goes to path."""
    for email in reversed(outbox):
        m = re.search(rf"{re.escape(path)}\?token=([\w-]+)", email.text)
        if m:
            return m.group(1)
    raise AssertionError(f"No email with a {path} link")


# --- Sign-up ---


def test_signup_creates_org_and_owner_and_signs_in(client):
    res = signup(client)
    assert res.status_code == 201
    me = client.get("/api/auth/me", headers=bearer(res)).json()
    assert me["email"] == "ann@acme.example"  # stored lowercase
    assert me["name"] == "Ann Owner"
    assert me["role"] == "owner"
    assert me["is_platform_admin"] is False
    assert me["email_verified"] is False
    assert me["organization"]["name"] == "Acme Ltd"


def test_signup_sends_a_verification_link(client):
    signup(client)
    [email] = outbox
    assert email.to == "ann@acme.example"
    assert f"{get_settings().app_url}/verify-email?token=" in email.text


def test_signup_with_a_taken_email_is_refused(client):
    signup(client)
    res = signup(client, email="ANN@acme.example", organization_name="Other")
    assert res.status_code == 409


def test_signup_validates_input(client):
    assert signup(client, password="short").status_code == 422
    assert signup(client, email="not-an-email").status_code == 422
    assert signup(client, organization_name="").status_code == 422


def test_each_signup_gets_its_own_organization(client):
    a = bearer(signup(client))
    b = bearer(signup(client, email="bo@other.example", organization_name="Other"))
    org_a = client.get("/api/auth/me", headers=a).json()["organization"]["id"]
    org_b = client.get("/api/auth/me", headers=b).json()["organization"]["id"]
    assert org_a != org_b


# --- Verification ---


def test_unverified_users_cant_save_or_test_connections(client):
    h = bearer(signup(client))
    assert client.get("/api/ifs-connections", headers=h).status_code == 200
    res = client.post("/api/ifs-connections", json=CONNECTION, headers=h)
    assert res.status_code == 403
    assert "Verify your email" in res.json()["detail"]


def test_verifying_unlocks_connections_and_link_works_once(client):
    h = bearer(signup(client))
    token = link_token("/verify-email")
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["email_verified"] is True
    assert client.post("/api/ifs-connections", json=CONNECTION, headers=h).status_code == 201
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400


def test_bad_or_expired_verification_links_are_refused(client):
    signup(client)
    assert client.post("/api/auth/verify-email", json={"token": "nope"}).status_code == 400
    with SessionLocal() as db:
        db.execute(update(AuthToken).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    assert client.post("/api/auth/verify-email", json={"token": link_token("/verify-email")}).status_code == 400


def test_resending_replaces_the_old_link(client):
    h = bearer(signup(client))
    first = link_token("/verify-email")
    assert client.post("/api/auth/resend-verification", headers=h).status_code == 200
    second = link_token("/verify-email")
    assert first != second
    assert client.post("/api/auth/verify-email", json={"token": first}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": second}).status_code == 200


def test_links_are_stored_hashed(client):
    signup(client)
    token = link_token("/verify-email")
    with SessionLocal() as db:
        stored = db.scalars(select(AuthToken.token_hash)).all()
    assert token not in stored


# --- Sign-in ---


def test_sign_in_with_email_ignores_case_and_spaces(client):
    signup(client)
    res = client.post("/api/auth/login", json={"email": "  ANN@acme.EXAMPLE ", "password": "correct horse"})
    assert res.status_code == 200


def test_sign_in_with_wrong_password_fails(client):
    signup(client)
    res = client.post("/api/auth/login", json={"email": "ann@acme.example", "password": "wrong horse"})
    assert res.status_code == 401


def test_older_users_still_sign_in_with_their_username(client, auth_headers):
    assert client.get("/api/auth/me", headers=auth_headers).json()["username"] == "admin"


def test_tokens_from_before_ids_were_the_subject_are_refused(client):
    old = jwt.encode(
        {"sub": "admin", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_admin_email_from_settings_lets_the_admin_sign_in_with_it(client):
    with SessionLocal() as db:
        seed_platform_admin(db, "admin", "admin123", "Boss@AtroNexus.example")
    assert login_headers(client, "boss@atronexus.example", "admin123")
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == "admin"))
        assert admin.email == "boss@atronexus.example"
        assert admin.email_verified_at is not None


# --- Password reset ---


def test_forgot_password_answers_the_same_for_unknown_emails(client):
    signup(client)
    known = client.post("/api/auth/forgot-password", json={"email": "ann@acme.example"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "ghost@acme.example"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert [e.to for e in outbox if "reset-password" in e.text] == ["ann@acme.example"]


def test_reset_password_changes_it_and_ends_old_sessions(client):
    old_session = bearer(signup(client))
    client.post("/api/auth/forgot-password", json={"email": "ann@acme.example"})
    token = link_token("/reset-password")

    res = client.post("/api/auth/reset-password", json={"token": token, "password": "new password!"})
    assert res.status_code == 200

    assert client.get("/api/auth/me", headers=old_session).status_code == 401
    assert client.post("/api/auth/login", json={"email": "ann@acme.example", "password": "correct horse"}).status_code == 401
    new_session = login_headers(client, "ann@acme.example", "new password!")
    me = client.get("/api/auth/me", headers=new_session).json()
    # The link reached their inbox, so the address is confirmed too.
    assert me["email_verified"] is True

    # The link works once.
    again = client.post("/api/auth/reset-password", json={"token": token, "password": "another one"})
    assert again.status_code == 400


def test_reset_links_expire_and_cant_verify_email(client):
    signup(client)
    client.post("/api/auth/forgot-password", json={"email": "ann@acme.example"})
    token = link_token("/reset-password")
    # A reset link isn't a verification link.
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 400
    with SessionLocal() as db:
        db.execute(update(AuthToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    res = client.post("/api/auth/reset-password", json={"token": token, "password": "new password!"})
    assert res.status_code == 400


def test_reset_password_needs_a_strong_enough_password(client):
    signup(client)
    client.post("/api/auth/forgot-password", json={"email": "ann@acme.example"})
    res = client.post("/api/auth/reset-password", json={"token": link_token("/reset-password"), "password": "short"})
    assert res.status_code == 422
