"""Roles, the team list, and invitations."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.email.sender import outbox
from app.models import ORG_SUSPENDED, Invitation, Organization, User
from tests.conftest import add_user, login_headers
from tests.test_capture import fake_ifs, make_connection, make_target  # noqa: F401

ORG = "Other Co"  # bob (owner) from the other_org_headers fixture


def sign_in_as(client, username: str, role: str) -> dict[str, str]:
    add_user(username, ORG, role=role)
    return login_headers(client, username, "pass1234")


def member_id(username: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.id).where(User.username == username))


def invite(client, headers, email="new@other.example", role="member"):
    return client.post("/api/team/invitations", json={"email": email, "role": role}, headers=headers)


def invite_token() -> str:
    for email in reversed(outbox):
        m = re.search(r"/invite\?token=([\w-]+)", email.text)
        if m:
            return m.group(1)
    raise AssertionError("no invitation email")


def accept(client, token, name="Nia New", password="welcome aboard"):
    return client.post(f"/api/public/invitations/{token}/accept", json={"name": name, "password": password})


# --- Roles on connections and capture pages ---


def test_members_can_look_but_not_change(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    member = sign_in_as(client, "mo", "member")

    assert client.get("/api/ifs-connections", headers=member).status_code == 200
    assert client.get(f"/api/capture/targets/{target['id']}", headers=member).status_code == 200
    assert client.get("/api/capture/captures", headers=member).status_code == 200

    body = {"name": "x", "base_url": "https://x.example.com", "auth_type": "basic", "username": "u", "secret": "p"}
    refused = [
        client.post("/api/ifs-connections", json=body, headers=member),
        client.put(f"/api/ifs-connections/{conn['id']}", json=body, headers=member),
        client.post(f"/api/ifs-connections/{conn['id']}/test", headers=member),
        client.delete(f"/api/ifs-connections/{conn['id']}", headers=member),
        client.post("/api/capture/targets", json={**target, "connection_id": conn["id"]}, headers=member),
        client.post(f"/api/capture/targets/{target['id']}/test", headers=member),
        client.delete(f"/api/capture/targets/{target['id']}", headers=member),
    ]
    assert [r.status_code for r in refused] == [403] * len(refused)


def test_admins_can_change_settings(client, other_org_headers, fake_ifs):
    admin = sign_in_as(client, "ada", "admin")
    make_connection(client, admin)


# --- Team list ---


def test_team_list_shows_only_this_organization(client, auth_headers, other_org_headers):
    sign_in_as(client, "mo", "member")
    names = [m["username"] for m in client.get("/api/team/members", headers=other_org_headers).json()]
    assert names == ["bob", "mo"]
    me = [m for m in client.get("/api/team/members", headers=other_org_headers).json() if m["is_me"]]
    assert [m["username"] for m in me] == ["bob"]
    assert "bob" not in [m["username"] for m in client.get("/api/team/members", headers=auth_headers).json()]


# --- Role changes and removal ---


def test_owner_promotes_and_demotes(client, other_org_headers):
    sign_in_as(client, "mo", "member")
    res = client.put(f"/api/team/members/{member_id('mo')}/role", json={"role": "admin"}, headers=other_org_headers)
    assert res.status_code == 200 and res.json()["role"] == "admin"
    res = client.put(f"/api/team/members/{member_id('mo')}/role", json={"role": "owner"}, headers=other_org_headers)
    assert res.json()["role"] == "owner"


def test_admins_cant_touch_owners_or_make_owners(client, other_org_headers):
    admin = sign_in_as(client, "ada", "admin")
    sign_in_as(client, "mo", "member")
    bob = member_id("bob")
    assert client.put(f"/api/team/members/{bob}/role", json={"role": "member"}, headers=admin).status_code == 403
    assert client.delete(f"/api/team/members/{bob}", headers=admin).status_code == 403
    assert client.put(f"/api/team/members/{member_id('mo')}/role", json={"role": "owner"}, headers=admin).status_code == 403
    assert client.put(f"/api/team/members/{member_id('mo')}/role", json={"role": "admin"}, headers=admin).status_code == 200


def test_members_cant_manage_the_team(client, other_org_headers):
    member = sign_in_as(client, "mo", "member")
    sign_in_as(client, "max", "member")
    assert client.put(f"/api/team/members/{member_id('max')}/role", json={"role": "admin"}, headers=member).status_code == 403
    assert client.delete(f"/api/team/members/{member_id('max')}", headers=member).status_code == 403
    assert client.get("/api/team/invitations", headers=member).status_code == 403
    assert invite(client, member).status_code == 403


def test_nobody_changes_or_removes_themselves(client, other_org_headers):
    bob = member_id("bob")
    assert client.put(f"/api/team/members/{bob}/role", json={"role": "admin"}, headers=other_org_headers).status_code == 403
    assert client.delete(f"/api/team/members/{bob}", headers=other_org_headers).status_code == 403


def test_the_last_owner_cant_be_demoted_or_removed(client, other_org_headers):
    # The API can't reach this today (nobody changes themselves), so test the
    # guard directly; it protects future paths like "leave organization".
    import pytest
    from fastapi import HTTPException

    from app.team.service import ensure_an_owner_remains

    with SessionLocal() as db:
        bob = db.scalar(select(User).where(User.username == "bob"))
        for new_role in ("admin", None):
            with pytest.raises(HTTPException) as exc:
                ensure_an_owner_remains(db, bob, new_role)
            assert exc.value.status_code == 409
        ensure_an_owner_remains(db, bob, "owner")  # staying owner is fine
    add_user("olga", ORG, role="owner")
    with SessionLocal() as db:
        bob = db.scalar(select(User).where(User.username == "bob"))
        ensure_an_owner_remains(db, bob, "member")  # olga remains


def test_removed_members_lose_access(client, other_org_headers):
    member = sign_in_as(client, "mo", "member")
    assert client.delete(f"/api/team/members/{member_id('mo')}", headers=other_org_headers).status_code == 204
    assert client.get("/api/auth/me", headers=member).status_code == 401


def test_other_organizations_members_answer_404(client, auth_headers, other_org_headers):
    sign_in_as(client, "mo", "member")
    mo = member_id("mo")
    assert client.put(f"/api/team/members/{mo}/role", json={"role": "admin"}, headers=auth_headers).status_code == 404
    assert client.delete(f"/api/team/members/{mo}", headers=auth_headers).status_code == 404


# --- Invitations ---


def test_invite_accept_and_join(client, other_org_headers):
    res = invite(client, other_org_headers, email="New@Other.example", role="admin")
    assert res.status_code == 201
    assert res.json()["email"] == "new@other.example"
    [email] = outbox
    assert email.to == "new@other.example"
    assert "Other Co" in email.subject

    token = invite_token()
    info = client.get(f"/api/public/invitations/{token}").json()
    assert info == {"organization_name": ORG, "email": "new@other.example", "role": "admin", "invited_by": "bob"}

    res = accept(client, token)
    assert res.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}).json()
    assert (me["organization"]["name"], me["role"], me["email_verified"], me["name"]) == (ORG, "admin", True, "Nia New")

    # Used up, and gone from the pending list.
    assert client.get(f"/api/public/invitations/{token}").status_code == 404
    assert accept(client, token).status_code == 404
    assert client.get("/api/team/invitations", headers=other_org_headers).json() == []


def test_invitations_list_and_revoke(client, other_org_headers):
    invite(client, other_org_headers)
    token = invite_token()
    [pending] = client.get("/api/team/invitations", headers=other_org_headers).json()
    assert pending["invited_by"] == "bob"
    assert client.delete(f"/api/team/invitations/{pending['id']}", headers=other_org_headers).status_code == 204
    assert client.get(f"/api/public/invitations/{token}").status_code == 404


def test_inviting_again_replaces_the_old_link(client, other_org_headers):
    invite(client, other_org_headers)
    first = invite_token()
    invite(client, other_org_headers)
    second = invite_token()
    assert client.get(f"/api/public/invitations/{first}").status_code == 404
    assert client.get(f"/api/public/invitations/{second}").status_code == 200
    assert len(client.get("/api/team/invitations", headers=other_org_headers).json()) == 1


def test_cant_invite_an_existing_account(client, other_org_headers):
    client.post("/api/auth/signup", json={"organization_name": "Elsewhere", "name": "E", "email": "e@x.example",
                                          "password": "long enough"})
    assert invite(client, other_org_headers, email="E@x.example").status_code == 409


def test_account_created_after_the_invite_blocks_accepting(client, other_org_headers):
    invite(client, other_org_headers, email="race@x.example")
    token = invite_token()
    client.post("/api/auth/signup", json={"organization_name": "Elsewhere", "name": "R", "email": "race@x.example",
                                          "password": "long enough"})
    assert accept(client, token).status_code == 409


def test_admins_cant_invite_owners(client, other_org_headers):
    admin = sign_in_as(client, "ada", "admin")
    assert invite(client, admin, role="owner").status_code == 403
    assert invite(client, admin, role="admin").status_code == 201
    assert invite(client, other_org_headers, email="o@x.example", role="owner").status_code == 201


def test_unverified_accounts_cant_invite(client):
    res = client.post("/api/auth/signup", json={"organization_name": "Fresh", "name": "F", "email": "f@x.example",
                                                "password": "long enough"})
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert invite(client, headers).status_code == 403


def test_expired_invitations_and_suspended_orgs_dont_work(client, other_org_headers):
    invite(client, other_org_headers)
    token = invite_token()
    with SessionLocal() as db:
        db.execute(update(Organization).where(Organization.name == ORG).values(status=ORG_SUSPENDED))
        db.commit()
    assert client.get(f"/api/public/invitations/{token}").status_code == 404
    with SessionLocal() as db:
        db.execute(update(Organization).where(Organization.name == ORG).values(status="active"))
        db.execute(update(Invitation).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    assert client.get(f"/api/public/invitations/{token}").status_code == 404
    assert client.get("/api/team/invitations", headers=other_org_headers).json() == []


def test_cant_revoke_another_organizations_invitation(client, auth_headers, other_org_headers):
    inv = invite(client, other_org_headers).json()
    assert client.delete(f"/api/team/invitations/{inv['id']}", headers=auth_headers).status_code == 404


def test_accepting_needs_a_real_password(client, other_org_headers):
    invite(client, other_org_headers)
    assert accept(client, invite_token(), password="short").status_code == 422
