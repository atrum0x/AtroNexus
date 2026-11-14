"""Approvals: the hook IFS calls, the approval page, and decisions sent back to IFS."""

import json
import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select, update

from app.approvals.models import ApprovalRequest
from app.db import SessionLocal
from app.email.sender import outbox
from app.ifs import client as ifs_client
from app.links.models import SecureLink
from app.usage.models import UsageEvent
from tests.conftest import add_user, login_headers
from tests.test_capture import make_connection

HOOK = "/api/hooks/ifs/approvals"
SVC = "/main/ifsapplications/projection/v1/CAtxApprovalHandling.svc"
TOKEN_A = "a" * 64
TOKEN_B = "b" * 64


class FakeIfsApprovals:
    """Plays IFS: OAuth2 token endpoint plus the CAtxApprovalHandling projection."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.status = "PENDING"  # what GetPrLineStatus says
        self.refuse: str | None = None  # an IFS error message for Approve/Reject
        self.down = False
        self.tokens = {"JOHN": TOKEN_A, "MARY": TOKEN_B}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 300})
        if self.down:
            raise httpx.ConnectError("IFS is down")
        if request.url.path == SVC + "/":
            return httpx.Response(200, json={"value": []})
        action = request.url.path.removeprefix(SVC + "/")
        body = json.loads(request.content or b"{}")
        self.calls.append((action, body))
        if self.tokens.get(body.get("FndUser")) != body.get("Token"):
            return httpx.Response(400, json={"error": {"message": "This approval link is not valid."}})
        if action == "GetPrLineStatus":
            summary = {"description": "Laptop (live)", "lineTotal": 500000, "currency": "LKR"}
            return httpx.Response(200, json={"value": json.dumps({"status": self.status, "summary": summary})})
        if action == "GetRejectReasons":
            return httpx.Response(200, json={"value": json.dumps([{"id": "PRICE", "description": "Too expensive"}])})
        if self.refuse:
            return httpx.Response(400, json={"error": {"message": self.refuse}})
        if self.status != "PENDING":
            return httpx.Response(200, json={"value": self.status})
        self.status = "SIGNED"
        return httpx.Response(200, json={"value": "APPROVED" if action == "ApprovePrLine" else "REJECTED"})


@pytest.fixture
def fake_ifs():
    fake = FakeIfsApprovals()
    ifs_client.transport = httpx.MockTransport(fake)
    ifs_client._tokens.clear()
    yield fake
    ifs_client.transport = None
    ifs_client._tokens.clear()


def message(**overrides) -> dict:
    return {
        "version": 1,
        "kind": "PR_LINE",
        "company": "10",
        "requisitionNo": "R1001",
        "lineNo": "1",
        "releaseNo": "1",
        "sequenceNo": 2,
        "route": 1,
        "issuedAt": int(datetime.now(timezone.utc).timestamp()),
        "approvers": [
            {"fndUser": "JOHN", "authorizeId": "JOHN", "name": "John Perera", "email": "John@Example.com", "token": TOKEN_A},
            {"fndUser": "MARY", "authorizeId": "MARY", "name": "Mary Silva", "email": "mary@example.com", "token": TOKEN_B},
        ],
        "summary": {"partNo": "P-100", "description": "Laptop", "quantity": 2, "unit": "pcs",
                    "lineTotal": 500000, "currency": "LKR", "supplierName": "Acme"},
        **overrides,
    }


@pytest.fixture
def setup(client, auth_headers, fake_ifs) -> dict:
    """Approvals switched on for the platform organization; returns its hook key."""
    conn = make_connection(client, auth_headers)
    key = client.post("/api/approvals/setup/hook-key", headers=auth_headers).json()["hook_key"]
    res = client.put("/api/approvals/setup", json={"connection_id": conn["id"], "enabled": True, "link_days": 7},
                     headers=auth_headers)
    assert res.status_code == 200, res.text
    return {"key": key, "connection": conn}


def send(client, key, body=None):
    return client.post(HOOK, json=body or message(), headers={"Authorization": f"Bearer {key}"})


def link_for(email: str) -> str:
    for e in reversed(outbox):
        if e.to == email:
            m = re.search(r"/a/([\w-]+)", e.text)
            if m:
                return m.group(1)
    raise AssertionError(f"no approval email to {email}")


# --- The hook ---


def test_hook_needs_a_known_key(client, setup):
    assert client.post(HOOK, json=message()).status_code == 401
    assert send(client, "wrong-key").status_code == 401


def test_hook_creates_a_request_and_emails_each_approver(client, setup):
    res = send(client, setup["key"])
    assert res.status_code == 200 and res.json() == {"received": 2}
    assert sorted(e.to for e in outbox) == ["john@example.com", "mary@example.com"]
    email = next(e for e in outbox if e.to == "john@example.com")
    assert "R1001 line 1" in email.subject
    assert "Laptop" in email.text and "500,000.00 LKR" in email.text
    with SessionLocal() as db:
        rows = db.scalars(select(ApprovalRequest)).all()
        assert {r.fnd_user for r in rows} == {"JOHN", "MARY"}
        assert all(TOKEN_A not in r.ifs_token_enc and TOKEN_B not in r.ifs_token_enc for r in rows)


def test_hook_refuses_when_switched_off(client, setup, auth_headers):
    client.put("/api/approvals/setup", json={"connection_id": setup["connection"]["id"], "enabled": False},
               headers=auth_headers)
    assert send(client, setup["key"]).status_code == 409
    client.put("/api/approvals/setup", json={"connection_id": setup["connection"]["id"], "enabled": True},
               headers=auth_headers)
    client.put("/api/tools/approvals", json={"enabled": False}, headers=auth_headers)
    assert send(client, setup["key"]).status_code == 409


def test_hook_rejects_unknown_message_kinds(client, setup):
    assert send(client, setup["key"], message(kind="PO_LINE")).status_code == 422
    assert send(client, setup["key"], message(version=2)).status_code == 422
    bad = message()
    bad["approvers"][0]["token"] = "not-hex"
    assert send(client, setup["key"], bad).status_code == 422


def test_a_new_key_stops_the_old_one(client, setup, auth_headers):
    new = client.post("/api/approvals/setup/hook-key", headers=auth_headers).json()["hook_key"]
    assert send(client, setup["key"]).status_code == 401
    assert send(client, new).status_code == 200


def test_sending_the_same_step_again_replaces_the_link(client, setup):
    send(client, setup["key"])
    first = link_for("john@example.com")
    send(client, setup["key"])
    second = link_for("john@example.com")
    assert first != second
    old = client.get(f"/api/public/approvals/{first}")
    assert old.status_code == 404 and "newer email" in old.json()["detail"]
    assert client.get(f"/api/public/approvals/{second}").json()["link_state"] == "open"


# --- The approval page ---


def test_page_shows_the_live_line_and_marks_the_link_opened(client, setup, fake_ifs):
    send(client, setup["key"])
    view = client.get(f"/api/public/approvals/{link_for('john@example.com')}").json()
    assert (view["link_state"], view["ifs_status"], view["live"]) == ("open", "PENDING", True)
    assert view["summary"]["description"] == "Laptop (live)"
    assert view["approver_name"] == "John Perera"
    action, body = fake_ifs.calls[-1]
    assert action == "GetPrLineStatus"
    assert (body["RequisitionNo"], body["SequenceNo"], body["FndUser"], body["Token"]) == ("R1001", 2, "JOHN", TOKEN_A)
    with SessionLocal() as db:
        assert db.scalar(select(SecureLink.opened_at).where(SecureLink.recipient_email == "john@example.com"))


def test_page_still_works_when_ifs_is_down(client, setup, fake_ifs):
    send(client, setup["key"])
    fake_ifs.down = True
    view = client.get(f"/api/public/approvals/{link_for('john@example.com')}").json()
    assert view["live"] is False
    assert view["summary"]["description"] == "Laptop"  # what IFS sent
    assert "Couldn't read the latest from IFS" in view["message"]


def test_unknown_links_answer_404(client, setup):
    assert client.get("/api/public/approvals/" + "x" * 43).status_code == 404


# --- Decisions ---


def decide(client, token, **body):
    return client.post(f"/api/public/approvals/{token}/decide", json=body)


def test_approve_records_it_and_closes_the_other_approvers(client, setup, fake_ifs):
    send(client, setup["key"])
    john, mary = link_for("john@example.com"), link_for("mary@example.com")
    res = decide(client, john, decision="approve")
    assert res.status_code == 200 and res.json()["result"] == "APPROVED"
    assert fake_ifs.calls[-1][0] == "ApprovePrLine"

    assert client.get(f"/api/public/approvals/{john}").json()["decision"] == "approved"
    assert client.get(f"/api/public/approvals/{mary}").json()["link_state"] == "revoked"
    assert decide(client, john, decision="approve").status_code == 409
    assert decide(client, mary, decision="approve").status_code == 409
    with SessionLocal() as db:
        events = db.scalars(select(UsageEvent).where(UsageEvent.tool == "approvals")).all()
        assert [(e.kind, e.billable) for e in events] == [("approvals.decided", True)]


def test_reject_needs_a_reason_and_passes_it_on(client, setup, fake_ifs):
    send(client, setup["key"])
    token = link_for("john@example.com")
    assert decide(client, token, decision="reject").status_code == 422
    reasons = client.get(f"/api/public/approvals/{token}/reject-reasons").json()
    assert reasons == [{"id": "PRICE", "description": "Too expensive"}]
    res = decide(client, token, decision="reject", reason_id="PRICE", note="Get another quote")
    assert res.json()["result"] == "REJECTED"
    action, body = fake_ifs.calls[-1]
    assert (action, body["RejectReasonId"], body["RejectNote"]) == ("RejectPrLine", "PRICE", "Get another quote")
    with SessionLocal() as db:
        row = db.scalar(select(ApprovalRequest).where(ApprovalRequest.fnd_user == "JOHN"))
        assert (row.status, row.reject_reason_id, row.note) == ("rejected", "PRICE", "Get another quote")


def test_when_ifs_refuses_the_link_stays_usable(client, setup, fake_ifs):
    send(client, setup["key"])
    token = link_for("john@example.com")
    fake_ifs.refuse = "Authorization limit exceeded for JOHN."
    res = decide(client, token, decision="approve")
    assert res.status_code == 422
    assert "Authorization limit exceeded" in res.json()["detail"]
    assert client.get(f"/api/public/approvals/{token}").json()["link_state"] == "open"
    fake_ifs.refuse = None
    assert decide(client, token, decision="reject", reason_id="PRICE").json()["result"] == "REJECTED"


def test_when_someone_already_signed_in_ifs_nothing_changes(client, setup, fake_ifs):
    send(client, setup["key"])
    token = link_for("john@example.com")
    fake_ifs.status = "SIGNED"
    res = decide(client, token, decision="approve")
    assert res.json()["result"] == "SIGNED"
    assert "already authorized" in res.json()["message"]
    assert client.get(f"/api/public/approvals/{token}").json()["decision"] == "closed"


def test_expired_links_cant_be_used(client, setup):
    send(client, setup["key"])
    token = link_for("john@example.com")
    with SessionLocal() as db:
        db.execute(update(SecureLink).values(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        db.commit()
    assert client.get(f"/api/public/approvals/{token}").json()["link_state"] == "expired"
    assert decide(client, token, decision="approve").status_code == 409


def test_links_stop_when_the_tool_is_switched_off(client, setup, auth_headers):
    send(client, setup["key"])
    token = link_for("john@example.com")
    client.put("/api/tools/approvals", json={"enabled": False}, headers=auth_headers)
    assert client.get(f"/api/public/approvals/{token}").status_code == 404


# --- Admin ---


def test_setup_validation(client, auth_headers, other_org_headers, fake_ifs):
    other_conn = make_connection(client, other_org_headers)
    res = client.put("/api/approvals/setup", json={"connection_id": other_conn["id"], "enabled": False},
                     headers=auth_headers)
    assert res.status_code == 422  # another organization's connection
    conn = make_connection(client, auth_headers)
    res = client.put("/api/approvals/setup", json={"connection_id": conn["id"], "enabled": True}, headers=auth_headers)
    assert res.status_code == 422  # no hook key yet
    setup = client.get("/api/approvals/setup", headers=auth_headers).json()
    assert setup["hook_url"].endswith(HOOK) and setup["has_hook_key"] is False


def test_hook_key_is_shown_once(client, auth_headers):
    key = client.post("/api/approvals/setup/hook-key", headers=auth_headers).json()["hook_key"]
    setup = client.get("/api/approvals/setup", headers=auth_headers).json()
    assert setup["has_hook_key"] and setup["hook_key_hint"] == key[-4:]
    assert key not in json.dumps(setup)


def test_check_package(client, setup, auth_headers, fake_ifs):
    res = client.post("/api/approvals/setup/check", headers=auth_headers).json()
    assert res["ok"] is True


def test_members_can_see_the_log_but_not_change_setup(client, other_org_headers):
    client.put("/api/tools/approvals", json={"enabled": True}, headers=other_org_headers)
    add_user("mo", "Other Co", role="member")
    member = login_headers(client, "mo", "pass1234")
    assert client.get("/api/approvals/requests", headers=member).status_code == 200
    assert client.post("/api/approvals/setup/hook-key", headers=member).status_code == 403


def test_request_log(client, setup, auth_headers):
    send(client, setup["key"])
    decide(client, link_for("john@example.com"), decision="approve")
    rows = client.get("/api/approvals/requests", headers=auth_headers).json()
    by_user = {r["approver_name"]: r for r in rows}
    assert by_user["John Perera"]["status"] == "approved"
    assert by_user["Mary Silva"]["status"] == "closed"
    assert by_user["John Perera"]["item"] == "Laptop"
    assert by_user["John Perera"]["line_total"] == "500,000.00 LKR"


def test_other_organizations_cant_see_the_log(client, setup, other_org_headers):
    send(client, setup["key"])
    client.put("/api/tools/approvals", json={"enabled": True}, headers=other_org_headers)
    assert client.get("/api/approvals/requests", headers=other_org_headers).json() == []


def test_tool_off_closes_the_admin_api(client, other_org_headers):
    assert client.get("/api/approvals/setup", headers=other_org_headers).status_code == 403


def test_package_download_is_ready_to_import(client, auth_headers):
    import io
    import zipfile

    res = client.get("/api/approvals/package", headers=auth_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "atronexus-approvals-ifs-package.zip" in res.headers["content-disposition"]
    files = zipfile.ZipFile(io.BytesIO(res.content))
    names = set(files.namelist())
    root = "atronexus-approvals/"
    for expected in (
        "README.md",
        "workspace/purch/source/purch/database/CAtxApprovalUtil-Cust.plsql",
        "workspace/purch/model/purch/CAtxApprovalHandling-Cust.projection",
        "config/connect/RoutingRule_C_ATX_APPROVAL_RULE.xml",
        "config/C_ATX_APPROVALS.zip",
    ):
        assert root + expected in names
    assert not any("config/appconfig/" in n for n in names)

    # The configuration package is a valid zip with the package XML at its root.
    acp = zipfile.ZipFile(io.BytesIO(files.read(root + "config/C_ATX_APPROVALS.zip")))
    assert "C_ATX_APPROVALS.xml" in acp.namelist()
    assert any(n.startswith("Items/CustomEventAction-") for n in acp.namelist())

    # The routing address points at this AtroNexus; the hook key isn't in it.
    address = files.read(root + "config/connect/RoutingAddress_C_ATX_APPROVAL_ADDR.xml").decode()
    assert "<REST_ROOT_END_POINT>http://localhost:3000/api/hooks/ifs/approvals</REST_ROOT_END_POINT>" in address
    assert "PASTE_YOUR_ATRONEXUS_HOOK_KEY_HERE" in address


def test_package_download_needs_the_tool(client, other_org_headers):
    assert client.get("/api/approvals/package", headers=other_org_headers).status_code == 403
