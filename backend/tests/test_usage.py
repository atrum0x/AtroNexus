"""Usage counting and the overview dashboard."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.usage import service
from app.usage.models import UsageEvent
from tests.conftest import add_user, login_headers
from tests.test_capture import CAPTURED, FakeIfs, fake_ifs, make_connection, make_target, public_url  # noqa: F401


def overview(client, headers) -> dict:
    res = client.get("/api/overview", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def capture_usage(data: dict) -> dict:
    return next(u for u in data["usage"] if u["tool"] == "capture")


def org_id_of(username: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(User.organization_id).where(User.username == username))


def test_sent_captures_count_as_billable_and_failures_dont(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    client.post(public_url(target, "REQ-1"), json=CAPTURED)  # sent
    client.post(public_url(target, "NOPE"), json=CAPTURED)  # IFS has no such request: failed

    with SessionLocal() as db:
        events = db.scalars(select(UsageEvent).order_by(UsageEvent.id)).all()
    assert [(e.kind, e.billable, e.organization_id) for e in events] == [
        ("capture.sent", True, org_id_of("bob")),
        ("capture.failed", False, org_id_of("bob")),
    ]
    assert events[0].ref.startswith("capture:")

    usage = capture_usage(overview(client, other_org_headers))
    assert (usage["succeeded"], usage["failed"], usage["enabled"]) == (1, 1, True)


def test_a_retry_that_succeeds_counts_both_attempts(client, other_org_headers):
    fake = FakeIfs(patch_status=400)
    from app.ifs import client as ifs_client
    import httpx

    ifs_client.transport = httpx.MockTransport(fake)
    ifs_client._tokens.clear()
    try:
        conn = make_connection(client, other_org_headers)
        target = make_target(client, other_org_headers, conn["id"])
        client.post(public_url(target), json=CAPTURED)  # refused by IFS
        fake.patch_status = 204
        client.post(public_url(target), json=CAPTURED)  # retried, accepted
    finally:
        ifs_client.transport = None
        ifs_client._tokens.clear()
    usage = capture_usage(overview(client, other_org_headers))
    assert (usage["succeeded"], usage["failed"]) == (1, 1)


def test_usage_is_per_organization(client, auth_headers, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    client.post(public_url(target), json=CAPTURED)
    mine = capture_usage(overview(client, auth_headers))
    assert (mine["succeeded"], mine["failed"]) == (0, 0)


def test_months_are_counted_separately(client, other_org_headers):
    org = org_id_of("bob")
    start = service.month_start(datetime.now(timezone.utc))
    with SessionLocal() as db:
        for when, n in ((start - timedelta(days=3), 4), (start - timedelta(days=40), 9), (start + timedelta(hours=1), 2)):
            for _ in range(n):
                db.add(UsageEvent(organization_id=org, tool="capture", kind="capture.sent", billable=True,
                                  created_at=when))
        db.commit()
    usage = capture_usage(overview(client, other_org_headers))
    assert (usage["succeeded"], usage["last_month_succeeded"]) == (2, 4)


def test_month_helpers_cross_the_year():
    jan = datetime(2027, 1, 15, 10, tzinfo=timezone.utc)
    start = service.month_start(jan)
    assert start == datetime(2027, 1, 1, tzinfo=timezone.utc)
    assert service.previous_month_start(start) == datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert service.next_month_start(datetime(2026, 12, 1, tzinfo=timezone.utc)) == start


def test_recent_errors_show_failed_captures_with_a_link(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    client.post(public_url(target, "NOPE"), json=CAPTURED)
    [error] = overview(client, other_org_headers)["recent_errors"]
    assert error["link"] == f"/capture/{target['id']}"
    assert "NOPE" in error["title"]
    assert "no capture request" in error["message"]


def test_estimate_adds_monthly_fees_and_usage_for_managers_only(client, other_org_headers, fake_ifs):
    est = overview(client, other_org_headers)["estimate"]
    [line] = est["lines"]
    assert line["tool"] == "capture"
    assert Decimal(line["monthly_fee"]) == Decimal(est["total"]) > 0
    assert Decimal(line["usage_cost"]) == 0  # capture has no per-use price

    add_user("mo", "Other Co", role="member")
    assert overview(client, login_headers(client, "mo", "pass1234"))["estimate"] is None


def test_estimate_counts_usage_prices(client, other_org_headers, monkeypatch):
    # Pretend capture had a per-use price, to check the sum.
    from dataclasses import replace

    from app.tools import catalog

    priced = replace(catalog.BY_CODE["capture"], usage_price=Decimal("0.10"), usage_unit="capture")
    monkeypatch.setattr(service, "TOOLS", tuple(priced if t.code == "capture" else t for t in catalog.TOOLS))
    org = org_id_of("bob")
    with SessionLocal() as db:
        for _ in range(3):
            db.add(UsageEvent(organization_id=org, tool="capture", kind="capture.sent", billable=True))
        db.add(UsageEvent(organization_id=org, tool="capture", kind="capture.failed", billable=False))
        db.commit()
    [line] = overview(client, other_org_headers)["estimate"]["lines"]
    assert Decimal(line["usage_cost"]) == Decimal("0.30")
    assert Decimal(line["total"]) == priced.monthly_price + Decimal("0.30")


def test_checklist_follows_setup(client, fake_ifs):
    res = client.post("/api/auth/signup", json={"organization_name": "Fresh", "name": "F", "email": "f@x.example",
                                                "password": "long enough"})
    h = {"Authorization": f"Bearer {res.json()['access_token']}"}

    def done():
        return {i["key"]: i["done"] for i in overview(client, h)["checklist"]}

    assert done() == {"verify_email": False, "tool": False, "connection": False, "team": False}
    client.put("/api/tools/capture", json={"enabled": True}, headers=h)
    assert done()["tool"] is True and done()["capture_page"] is False
    client.post("/api/team/invitations", json={"email": "x@x.example"}, headers=h)  # refused: unverified
    assert done()["team"] is False


def test_switched_off_tools_with_usage_this_month_still_show(client, other_org_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    client.post(public_url(target), json=CAPTURED)
    client.put("/api/tools/capture", json={"enabled": False}, headers=other_org_headers)
    data = overview(client, other_org_headers)
    usage = capture_usage(data)
    assert (usage["enabled"], usage["succeeded"]) == (False, 1)
    assert data["estimate"]["lines"] == []  # nothing on, nothing to pay
