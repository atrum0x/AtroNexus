"""The platform admin's view of every customer."""

from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Organization
from tests.conftest import add_user, login_headers
from tests.test_capture import CAPTURED, fake_ifs, make_connection, make_target, public_url  # noqa: F401


def org_id(name: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(Organization.id).where(Organization.name == name))


def overview(client, headers) -> dict:
    res = client.get("/api/platform/organizations", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def set_status(client, headers, org, status, reason=None):
    return client.put(f"/api/platform/organizations/{org}/status", json={"status": status, "reason": reason},
                      headers=headers)


def test_only_platform_admins_see_it(client, other_org_headers):
    # Owners of customer organizations get 404, as if it didn't exist.
    assert client.get("/api/platform/organizations", headers=other_org_headers).status_code == 404
    assert client.get(f"/api/platform/organizations/{org_id('Other Co')}", headers=other_org_headers).status_code == 404
    assert set_status(client, other_org_headers, org_id("AtroNexus"), "suspended").status_code == 404
    assert client.get("/api/platform/organizations").status_code == 401


def test_me_says_who_is_a_platform_admin(client, auth_headers, other_org_headers):
    assert client.get("/api/auth/me", headers=auth_headers).json()["is_platform_admin"] is True
    assert client.get("/api/auth/me", headers=other_org_headers).json()["is_platform_admin"] is False


def test_overview_lists_every_organization_with_numbers(client, auth_headers, other_org_headers, fake_ifs):
    add_user("mo", "Other Co", role="member")
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    client.post(public_url(target, "REQ-1"), json=CAPTURED)
    client.post(public_url(target, "NOPE"), json=CAPTURED)

    data = overview(client, auth_headers)
    rows = {r["name"]: r for r in data["organizations"]}
    assert set(rows) == {"AtroNexus", "Other Co"}
    other = rows["Other Co"]
    assert (other["owner"], other["members"], other["tools"]) == ("bob", 2, ["capture"])
    assert (other["usage_succeeded"], other["usage_failed"]) == (1, 1)
    assert Decimal(other["estimated_revenue"]) == Decimal("29")
    assert other["last_activity"] is not None

    s = data["summary"]
    assert (s["organizations"], s["active"], s["suspended"], s["users"]) == (2, 2, 0, 3)
    assert (s["usage_succeeded"], s["usage_failed"]) == (1, 1)
    # The platform org has every available tool on; Other Co only the capture page.
    from app.tools.catalog import BY_CODE, TOOLS

    platform_fees = sum((t.monthly_price for t in TOOLS if t.available), Decimal(0))
    assert Decimal(s["estimated_revenue"]) == platform_fees + BY_CODE["capture"].monthly_price


def test_detail_shows_members_tools_history_and_errors(client, auth_headers, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    client.post(public_url(target, "NOPE"), json=CAPTURED)
    client.put("/api/tools/capture", json={"enabled": False}, headers=other_org_headers)
    client.put("/api/tools/capture", json={"enabled": True}, headers=other_org_headers)

    res = client.get(f"/api/platform/organizations/{org_id('Other Co')}", headers=auth_headers)
    d = res.json()
    assert [m["username"] for m in d["members"]] == ["bob"]
    [tool] = d["tools"]
    assert (tool["tool"], tool["enabled"], tool["failed"]) == ("capture", True, 1)
    # Newest first; bob switched it off then on.
    assert [(h["enabled"], h["by"]) for h in d["tool_history"]][:2] == [(True, "bob"), (False, "bob")]
    assert (d["connections"], d["capture_pages"]) == (1, 1)
    assert "NOPE" in d["recent_errors"][0]["title"]
    assert d["is_platform_org"] is False


def test_unknown_organization_is_404(client, auth_headers):
    assert client.get("/api/platform/organizations/9999", headers=auth_headers).status_code == 404
    assert set_status(client, auth_headers, 9999, "suspended").status_code == 404


def test_suspend_and_reactivate(client, auth_headers, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    other = org_id("Other Co")

    res = set_status(client, auth_headers, other, "suspended", "  Unpaid invoice  ")
    assert res.status_code == 200
    assert (res.json()["status"], res.json()["status_reason"]) == ("suspended", "Unpaid invoice")
    assert res.json()["status_changed_at"] is not None
    # Suspended: no sign-in, no sessions, no public links, no revenue counted.
    assert client.post("/api/auth/login", json={"email": "bob", "password": "pass1234"}).status_code == 403
    assert client.get("/api/auth/me", headers=other_org_headers).status_code == 403
    assert client.get(public_url(target)).status_code == 404
    row = {r["name"]: r for r in overview(client, auth_headers)["organizations"]}["Other Co"]
    assert Decimal(row["estimated_revenue"]) == 0
    assert overview(client, auth_headers)["summary"]["suspended"] == 1

    res = set_status(client, auth_headers, other, "active")
    assert res.json()["status"] == "active"
    assert login_headers(client, "bob", "pass1234")
    assert client.get(public_url(target)).status_code == 200


def test_cant_suspend_the_platforms_own_organization(client, auth_headers):
    res = set_status(client, auth_headers, org_id("AtroNexus"), "suspended")
    assert res.status_code == 409
    assert client.get("/api/auth/me", headers=auth_headers).status_code == 200


def test_reason_is_limited(client, auth_headers, other_org_headers):
    res = set_status(client, auth_headers, org_id("Other Co"), "suspended", "x" * 501)
    assert res.status_code == 422
