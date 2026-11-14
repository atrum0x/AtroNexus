"""Switching tools on and off per organization."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import ToolEvent, User
from tests.conftest import add_user, login_headers
from tests.test_capture import CAPTURED, fake_ifs, make_connection, make_target, public_url  # noqa: F401


def tools(client, headers) -> dict[str, dict]:
    return {t["code"]: t for t in client.get("/api/tools", headers=headers).json()}


def switch(client, headers, code, enabled):
    return client.put(f"/api/tools/{code}", json={"enabled": enabled}, headers=headers)


def signup(client, email="new@x.example"):
    res = client.post("/api/auth/signup", json={"organization_name": "Newco", "name": "N", "email": email,
                                                "password": "long enough"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def test_catalog_lists_every_tool_with_prices(client, auth_headers):
    listed = tools(client, auth_headers)
    assert len(listed) == 7
    capture = listed["capture"]
    assert capture["available"] is True
    assert float(capture["monthly_price"]) > 0
    messaging = listed["messaging"]
    assert messaging["available"] is True
    assert messaging["usage_unit"] == "message"


def test_platform_org_has_the_available_tools_on(client, auth_headers):
    assert tools(client, auth_headers)["capture"]["enabled"] is True


def test_new_signups_start_with_no_tools(client):
    h = signup(client)
    assert [c for c, t in tools(client, h).items() if t["enabled"]] == []
    res = client.get("/api/capture/targets", headers=h)
    assert res.status_code == 403
    assert "switched off" in res.json()["detail"]


def test_owner_switches_a_tool_on_and_off(client):
    h = signup(client)
    res = switch(client, h, "capture", True)
    assert res.status_code == 200 and res.json()["enabled"] is True
    assert client.get("/api/capture/targets", headers=h).status_code == 200
    assert switch(client, h, "capture", False).json()["enabled"] is False
    assert client.get("/api/capture/targets", headers=h).status_code == 403


def test_switching_is_logged_with_who_did_it(client):
    h = signup(client)
    switch(client, h, "capture", True)
    switch(client, h, "capture", True)  # no change, no event
    switch(client, h, "capture", False)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "new@x.example"))
        events = db.scalars(
            select(ToolEvent).where(ToolEvent.organization_id == user.organization_id).order_by(ToolEvent.id)
        ).all()
    assert [(e.tool, e.enabled, e.user_id) for e in events] == [
        ("capture", True, user.id),
        ("capture", False, user.id),
    ]


def test_tools_that_arent_built_cant_be_switched_on(client, auth_headers):
    res = switch(client, auth_headers, "email_in", True)
    assert res.status_code == 409
    assert switch(client, auth_headers, "nope", True).status_code == 404


def test_members_cant_switch_tools(client, other_org_headers):
    add_user("mo", "Other Co", role="member")
    member = login_headers(client, "mo", "pass1234")
    assert tools(client, member)["capture"]["enabled"] is True  # can look
    assert switch(client, member, "capture", False).status_code == 403


def test_switching_off_stops_capture_links_and_keeps_the_data(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    assert client.post(public_url(target), json=CAPTURED).status_code == 200

    switch(client, other_org_headers, "capture", False)
    assert client.get(public_url(target, "REQ-2")).status_code == 404
    assert client.post(public_url(target, "REQ-2"), json=CAPTURED).status_code == 404
    # IFS connections are shared by every tool, so they stay available.
    assert client.get("/api/ifs-connections", headers=other_org_headers).status_code == 200

    switch(client, other_org_headers, "capture", True)
    assert client.get(public_url(target, "REQ-2")).status_code == 200
    assert len(client.get("/api/capture/captures", headers=other_org_headers).json()) == 1


def test_one_orgs_switch_doesnt_affect_another(client, auth_headers, other_org_headers):
    switch(client, other_org_headers, "capture", False)
    assert tools(client, auth_headers)["capture"]["enabled"] is True
    assert client.get("/api/capture/targets", headers=auth_headers).status_code == 200
