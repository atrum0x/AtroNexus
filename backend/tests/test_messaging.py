"""Messaging hub: templates to WhatsApp (Meta), scenarios, messages from IFS, and Meta's webhook."""

import hashlib
import hmac
import io
import json
import zipfile

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.messaging import meta
from app.messaging.models import Message
from app.usage.models import UsageEvent
from tests.conftest import add_user, login_headers

HOOK = "/api/hooks/ifs/messages"
WEBHOOK = "/api/hooks/meta/whatsapp"
GRAPH = "https://graph.example.test/v23.0"
WABA = "waba-1"
PHONE_ID = "phone-1"
APP_SECRET = "app-secret-for-tests"

TEMPLATE = {
    "name": "order_shipped",
    "language": "en",
    "category": "UTILITY",
    "header_text": "Order {{1}}",
    "body_text": "Hi {{1}}, your order {{2}} has shipped. Expected on {{3}}.",
    "footer_text": "Sent by AtroNexus",
    "buttons": [{"type": "URL", "text": "Track", "url": "https://track.example.com/o/{{1}}"},
                {"type": "QUICK_REPLY", "text": "Thanks"}],
    "body_examples": ["Acme", "C1001", "1 Dec"],
    "header_example": "C1001",
    "button_examples": {"0": "C1001"},
}


class FakeMeta:
    """Plays graph.facebook.com for the WhatsApp Cloud API."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.template_status = "APPROVED"
        self.send_error: str | None = None
        self.next_id = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/v23.0/")
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, path, body))
        assert request.headers["authorization"] == "Bearer wa-token"
        if path == f"{WABA}/message_templates" and request.method == "POST":
            if body["name"].endswith("_taken"):
                return httpx.Response(400, json={"error": {"message": "x", "error_user_msg": "Name already used."}})
            return httpx.Response(200, json={"id": "tmpl-1", "status": "PENDING", "category": body["category"]})
        if path == f"{WABA}/message_templates" and request.method == "DELETE":
            return httpx.Response(200, json={"success": True})
        if path == "tmpl-1":
            return httpx.Response(200, json={"id": "tmpl-1", "status": self.template_status, "rejected_reason": "NONE"})
        if path == f"{PHONE_ID}/messages":
            if self.send_error:
                return httpx.Response(400, json={"error": {"message": "(#131026) Message undeliverable",
                                                           "code": 131026,
                                                           "error_data": {"details": self.send_error}}})
            self.next_id += 1
            return httpx.Response(200, json={"messages": [{"id": f"wamid.{self.next_id}"}]})
        return httpx.Response(404, json={"error": {"message": "unknown path " + path}})

    def sends(self) -> list[dict]:
        return [b for m, p, b in self.calls if p == f"{PHONE_ID}/messages"]


@pytest.fixture
def whatsapp(monkeypatch):
    s = get_settings()
    for name, value in {
        "whatsapp_business_account_id": WABA,
        "whatsapp_phone_number_id": PHONE_ID,
        "whatsapp_access_token": "wa-token",
        "whatsapp_display_number": "+94 70 000 0000",
        "meta_app_secret": APP_SECRET,
        "meta_webhook_verify_token": "verify-me",
        "meta_graph_url": GRAPH,
    }.items():
        monkeypatch.setattr(s, name, value)
    fake = FakeMeta()
    meta.transport = httpx.MockTransport(fake)
    yield fake
    meta.transport = None


def tool_on(client, headers):
    assert client.put("/api/tools/messaging", json={"enabled": True}, headers=headers).status_code == 200


@pytest.fixture
def ready(client, auth_headers, whatsapp) -> dict:
    """Messaging on, an approved template, a scenario, and a hook key."""
    tool_on(client, auth_headers)
    t = client.post("/api/messaging/templates", json=TEMPLATE, headers=auth_headers)
    assert t.status_code == 201, t.text
    signed_webhook(client, template_event(t.json()["id"]))
    s = client.post("/api/messaging/scenarios", json={
        "code": "order_shipped", "name": "Order shipped", "template_id": t.json()["id"],
        "recipient": "{phone}", "header_param": "{orderNo}",
        "body_params": ["{customer.name}", "{orderNo}", "{date}"], "button_params": {"0": "{orderNo}"},
    }, headers=auth_headers)
    assert s.status_code == 201, s.text
    key = client.post("/api/messaging/setup/hook-key", headers=auth_headers).json()["hook_key"]
    res = client.put("/api/messaging/setup", json={"enabled": True, "default_country_code": "94"},
                     headers=auth_headers)
    assert res.status_code == 200, res.text
    return {"key": key, "template": t.json(), "scenario": s.json()}


def template_event(_template_id, event="APPROVED", reason=None) -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": WABA, "changes": [{
        "field": "message_template_status_update",
        "value": {"event": event, "message_template_id": "tmpl-1", "reason": reason}}]}]}


def status_event(meta_id: str, status: str, **extra) -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": WABA, "changes": [{
        "field": "messages",
        "value": {"statuses": [{"id": meta_id, "status": status, "timestamp": "1794600000", **extra}]}}]}]}


def signed_webhook(client, payload: dict, secret: str = APP_SECRET):
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(WEBHOOK, content=raw, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})


def from_ifs(client, key, **overrides):
    body = {"version": 1, "scenario": "ORDER_SHIPPED",
            "params": {"phone": "077 123 4567", "customer": {"name": "Acme"}, "orderNo": "C1001", "date": "1 Dec"},
            **overrides}
    return client.post(HOOK, json=body, headers={"Authorization": f"Bearer {key}"})


# --- Templates ---


def test_a_template_goes_to_whatsapp_for_review(client, auth_headers, whatsapp):
    tool_on(client, auth_headers)
    res = client.post("/api/messaging/templates", json=TEMPLATE, headers=auth_headers)
    assert res.status_code == 201, res.text
    t = res.json()
    assert (t["status"], t["meta_name"]) == ("pending", "atx1_order_shipped")
    assert (t["body_variables"], t["header_has_variable"], t["url_buttons_with_variable"]) == (3, True, [0])
    method, path, payload = whatsapp.calls[-1]
    assert (method, path) == ("POST", f"{WABA}/message_templates")
    assert payload["name"] == "atx1_order_shipped" and payload["category"] == "UTILITY"
    parts = {c["type"]: c for c in payload["components"]}
    assert parts["HEADER"]["example"] == {"header_text": ["C1001"]}
    assert parts["BODY"]["example"] == {"body_text": [["Acme", "C1001", "1 Dec"]]}
    assert parts["BUTTONS"]["buttons"][0]["example"] == ["https://track.example.com/o/C1001"]
    assert parts["BUTTONS"]["buttons"][1] == {"type": "QUICK_REPLY", "text": "Thanks"}


@pytest.mark.parametrize("change, message", [
    ({"name": "Order Shipped"}, "lowercase"),
    ({"body_text": "Hi {{1}}, order {{3}} shipped."}, "without gaps"),
    ({"body_text": "{{1}} your order {{2}} shipped {{3}}"}, "start or end"),
    ({"body_examples": ["Acme", "C1001"]}, "example value for every variable"),
    ({"header_text": "Order {{2}}"}, "header can have one variable"),
    ({"footer_text": "By {{1}}"}, "footer can't have variables"),
    ({"buttons": [{"type": "URL", "text": "Track", "url": "https://x.example/{{1}}/info"}]}, "can end with {{1}}"),
    ({"buttons": [{"type": "URL", "text": "Track", "url": "http://x.example/"}]}, "https://"),
])
def test_template_rules_are_checked_before_whatsapp(client, auth_headers, whatsapp, change, message):
    tool_on(client, auth_headers)
    res = client.post("/api/messaging/templates", json={**TEMPLATE, **change}, headers=auth_headers)
    assert res.status_code == 422 and message in res.json()["detail"]
    assert whatsapp.calls == []


def test_without_whatsapp_a_template_stays_a_draft(client, auth_headers, whatsapp, monkeypatch):
    tool_on(client, auth_headers)
    monkeypatch.setattr(get_settings(), "whatsapp_access_token", None)
    t = client.post("/api/messaging/templates", json=TEMPLATE, headers=auth_headers).json()
    assert t["status"] == "draft" and "isn't connected" in t["status_reason"]
    monkeypatch.setattr(get_settings(), "whatsapp_access_token", "wa-token")
    t = client.post(f"/api/messaging/templates/{t['id']}/refresh", headers=auth_headers).json()
    assert t["status"] == "pending"


def test_whatsapps_refusal_is_shown_and_a_draft_can_be_fixed(client, auth_headers, whatsapp):
    tool_on(client, auth_headers)
    t = client.post("/api/messaging/templates", json={**TEMPLATE, "name": "order_taken"}, headers=auth_headers).json()
    assert t["status"] == "draft" and "Name already used." in t["status_reason"]
    res = client.put(f"/api/messaging/templates/{t['id']}", json=TEMPLATE, headers=auth_headers)
    assert res.json()["status"] == "pending"
    # Once WhatsApp has it, it can't be changed.
    res = client.put(f"/api/messaging/templates/{t['id']}", json=TEMPLATE, headers=auth_headers)
    assert res.status_code == 409


def test_review_result_arrives_by_webhook_or_refresh(client, auth_headers, whatsapp):
    tool_on(client, auth_headers)
    t = client.post("/api/messaging/templates", json=TEMPLATE, headers=auth_headers).json()
    assert signed_webhook(client, template_event(t["id"], "REJECTED", "INVALID_FORMAT")).status_code == 200
    t = client.get(f"/api/messaging/templates/{t['id']}", headers=auth_headers).json()
    assert (t["status"], t["status_reason"]) == ("rejected", "INVALID_FORMAT")
    whatsapp.template_status = "APPROVED"
    t = client.post(f"/api/messaging/templates/{t['id']}/refresh", headers=auth_headers).json()
    assert (t["status"], t["status_reason"]) == ("approved", None)


def test_deleting_a_template(client, auth_headers, ready, whatsapp):
    tid = ready["template"]["id"]
    assert client.delete(f"/api/messaging/templates/{tid}", headers=auth_headers).status_code == 409  # in use
    client.delete(f"/api/messaging/scenarios/{ready['scenario']['id']}", headers=auth_headers)
    assert client.delete(f"/api/messaging/templates/{tid}", headers=auth_headers).status_code == 204
    method, path, _ = whatsapp.calls[-1]
    assert (method, path) == ("DELETE", f"{WABA}/message_templates")


# --- Scenarios ---


def test_scenario_mapping_must_fit_the_template(client, auth_headers, ready):
    base = {"code": "OTHER", "name": "Other", "template_id": ready["template"]["id"], "recipient": "{phone}",
            "header_param": "{orderNo}", "body_params": ["{a}", "{b}", "{c}"], "button_params": {"0": "{orderNo}"}}
    ok = client.post("/api/messaging/scenarios", json=base, headers=auth_headers)
    assert ok.status_code == 201 and ok.json()["fields"] == ["phone", "orderNo", "a", "b", "c"]
    for change in ({"body_params": ["{a}", "{b}"]}, {"header_param": None}, {"button_params": {}},
                   {"recipient": " "}, {"code": "9BAD"}):
        res = client.post("/api/messaging/scenarios", json={**base, "code": "X1", **change}, headers=auth_headers)
        assert res.status_code == 422, change
    assert client.post("/api/messaging/scenarios", json=base, headers=auth_headers).status_code == 409  # same code


# --- Messages from IFS ---


def test_ifs_sends_a_message(client, ready, auth_headers, whatsapp):
    res = from_ifs(client, ready["key"], messageId="m-1")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "sent"
    sent = whatsapp.sends()[-1]
    assert sent["to"] == "94771234567"
    tpl = sent["template"]
    assert (tpl["name"], tpl["language"]) == ("atx1_order_shipped", {"code": "en"})
    assert tpl["components"] == [
        {"type": "header", "parameters": [{"type": "text", "text": "C1001"}]},
        {"type": "body", "parameters": [{"type": "text", "text": "Acme"}, {"type": "text", "text": "C1001"},
                                        {"type": "text", "text": "1 Dec"}]},
        {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": "C1001"}]},
    ]
    log = client.get("/api/messaging/messages", headers=auth_headers).json()
    assert log[0]["text"] == "Order C1001\nHi Acme, your order C1001 has shipped. Expected on 1 Dec."
    assert (log[0]["source"], log[0]["scenario_code"], log[0]["status"]) == ("ifs", "ORDER_SHIPPED", "sent")
    with SessionLocal() as db:
        events = db.scalars(select(UsageEvent).where(UsageEvent.tool == "messaging")).all()
        assert [(e.kind, e.billable) for e in events] == [("messaging.sent", True)]


def test_a_resend_from_ifs_isnt_sent_twice(client, ready, whatsapp):
    first = from_ifs(client, ready["key"], messageId="m-1").json()
    again = from_ifs(client, ready["key"], messageId="m-1").json()
    assert again["id"] == first["id"] and len(whatsapp.sends()) == 1
    from_ifs(client, ready["key"], messageId="m-2")
    assert len(whatsapp.sends()) == 2


def test_when_whatsapp_refuses_ifs_gets_an_error_and_can_resend(client, ready, whatsapp):
    whatsapp.send_error = "Message undeliverable"
    res = from_ifs(client, ready["key"], messageId="m-1")
    assert res.status_code == 502 and res.json()["error"] == "Message undeliverable"
    with SessionLocal() as db:
        events = db.scalars(select(UsageEvent).where(UsageEvent.tool == "messaging")).all()
        assert [(e.kind, e.billable) for e in events] == [("messaging.failed", False)]
    whatsapp.send_error = None
    res = from_ifs(client, ready["key"], messageId="m-1")
    assert res.status_code == 200 and res.json()["status"] == "sent"
    with SessionLocal() as db:
        assert len(db.scalars(select(Message)).all()) == 1  # the same message, retried


@pytest.mark.parametrize("change, code, text", [
    ({"scenario": "NOPE"}, 422, "no scenario NOPE"),
    ({"params": {"phone": "0771234567"}}, 422, "didn't send {orderNo}"),
    ({"params": {"phone": "12", "customer": {"name": "A"}, "orderNo": "1", "date": "x"}}, 422, "isn't a phone number"),
    ({"params": {"phone": "0771234567", "customer": {"name": " "}, "orderNo": "1", "date": "x"}}, 422, "came out empty"),
    ({"version": 2}, 422, "version"),
])
def test_ifs_gets_a_clear_reason_when_nothing_can_be_sent(client, ready, whatsapp, change, code, text):
    res = from_ifs(client, ready["key"], **change)
    assert res.status_code == code and text in res.json()["detail"]
    assert whatsapp.sends() == []


def test_values_are_tidied_for_whatsapp(client, ready, whatsapp):
    params = {"phone": "+94 (77) 123-4567", "customer": {"name": "Acme\nLanka   Ltd"}, "orderNo": 1001, "date": "1 Dec"}
    assert from_ifs(client, ready["key"], params=params).status_code == 200
    sent = whatsapp.sends()[-1]
    assert sent["to"] == "94771234567"
    assert sent["template"]["components"][1]["parameters"][0]["text"] == "Acme Lanka Ltd"
    assert sent["template"]["components"][1]["parameters"][1]["text"] == "1001"


def test_local_numbers_need_a_default_country_code(client, ready, auth_headers):
    client.put("/api/messaging/setup", json={"enabled": True, "default_country_code": None}, headers=auth_headers)
    res = from_ifs(client, ready["key"])
    assert res.status_code == 422 and "local number" in res.json()["detail"]


def test_hook_refusals(client, ready, auth_headers, whatsapp):
    assert from_ifs(client, "wrong").status_code == 401
    scenario = ready["scenario"]
    body = {k: scenario[k] for k in ("code", "name", "template_id", "recipient", "header_param", "body_params",
                                     "button_params")}
    client.put(f"/api/messaging/scenarios/{scenario['id']}", json={**body, "enabled": False}, headers=auth_headers)
    assert from_ifs(client, ready["key"]).status_code == 409
    client.put(f"/api/messaging/scenarios/{scenario['id']}", json={**body, "enabled": True}, headers=auth_headers)
    signed_webhook(client, template_event(None, "PAUSED"))
    res = from_ifs(client, ready["key"])
    assert res.status_code == 409 and "isn't approved" in res.json()["detail"]
    signed_webhook(client, template_event(None, "APPROVED"))
    client.put("/api/messaging/setup", json={"enabled": False}, headers=auth_headers)
    assert from_ifs(client, ready["key"]).status_code == 409
    client.put("/api/messaging/setup", json={"enabled": True, "default_country_code": "94"}, headers=auth_headers)
    client.put("/api/tools/messaging", json={"enabled": False}, headers=auth_headers)
    assert from_ifs(client, ready["key"]).status_code == 409
    assert whatsapp.sends() == []


def test_test_send(client, ready, auth_headers, whatsapp):
    res = client.post(f"/api/messaging/scenarios/{ready['scenario']['id']}/test", json={"params": {
        "phone": "+94771234567", "customer": {"name": "Test"}, "orderNo": "T1", "date": "today"}},
        headers=auth_headers)
    assert res.status_code == 200, res.text
    assert (res.json()["source"], res.json()["status"]) == ("test", "sent")
    res = client.post(f"/api/messaging/scenarios/{ready['scenario']['id']}/test", json={"params": {}},
                      headers=auth_headers)
    assert res.status_code == 422


# --- Meta's webhook ---


def test_delivery_reports_update_the_log(client, ready, auth_headers):
    from_ifs(client, ready["key"])
    assert signed_webhook(client, status_event("wamid.1", "read")).status_code == 200
    signed_webhook(client, status_event("wamid.1", "delivered"))  # late, out of order
    m = client.get("/api/messaging/messages", headers=auth_headers).json()[0]
    assert m["status"] == "read" and m["read_at"] and m["delivered_at"]

    from_ifs(client, ready["key"])
    signed_webhook(client, status_event("wamid.2", "failed", errors=[
        {"code": 131047, "title": "Re-engagement message", "error_data": {"details": "More than 24 hours passed."}}]))
    m = client.get("/api/messaging/messages", headers=auth_headers).json()[0]
    assert (m["status"], m["error"]) == ("failed", "More than 24 hours passed.")


def test_webhook_needs_metas_signature(client, ready):
    assert signed_webhook(client, status_event("wamid.1", "read"), secret="wrong").status_code == 401
    assert client.post(WEBHOOK, json=status_event("wamid.1", "read")).status_code == 401


def test_webhook_verification(client, whatsapp):
    ok = client.get(WEBHOOK, params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get(WEBHOOK, params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
    assert bad.status_code == 403


# --- Organizations, roles, tool switch ---


def test_other_organizations_see_nothing(client, ready, other_org_headers):
    tool_on(client, other_org_headers)
    assert client.get("/api/messaging/templates", headers=other_org_headers).json() == []
    assert client.get("/api/messaging/scenarios", headers=other_org_headers).json() == []
    assert client.get("/api/messaging/messages", headers=other_org_headers).json() == []
    tid, sid = ready["template"]["id"], ready["scenario"]["id"]
    assert client.get(f"/api/messaging/templates/{tid}", headers=other_org_headers).status_code == 404
    assert client.get(f"/api/messaging/scenarios/{sid}", headers=other_org_headers).status_code == 404
    assert client.post(f"/api/messaging/scenarios/{sid}/test", json={}, headers=other_org_headers).status_code == 404
    res = client.post("/api/messaging/scenarios", json={
        "code": "MINE", "name": "Mine", "template_id": tid, "recipient": "{phone}"}, headers=other_org_headers)
    assert res.status_code == 422  # can't use another organization's template


def test_members_read_only(client, other_org_headers, whatsapp):
    tool_on(client, other_org_headers)
    add_user("mm", "Other Co", role="member")
    member = login_headers(client, "mm", "pass1234")
    assert client.get("/api/messaging/templates", headers=member).status_code == 200
    assert client.post("/api/messaging/templates", json=TEMPLATE, headers=member).status_code == 403
    assert client.post("/api/messaging/setup/hook-key", headers=member).status_code == 403


def test_tool_off_closes_the_admin_api(client, other_org_headers):
    assert client.get("/api/messaging/setup", headers=other_org_headers).status_code == 403


def test_setup_and_package(client, auth_headers, whatsapp):
    tool_on(client, auth_headers)
    setup = client.get("/api/messaging/setup", headers=auth_headers).json()
    assert setup["sender"] == {"kind": "shared", "connected": True, "display_number": "+94 70 000 0000"}
    assert setup["hook_url"].endswith(HOOK)
    assert client.put("/api/messaging/setup", json={"enabled": True}, headers=auth_headers).status_code == 422
    res = client.put("/api/messaging/setup", json={"default_country_code": "+94"}, headers=auth_headers)
    assert res.status_code == 422

    res = client.get("/api/messaging/package", headers=auth_headers)
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    files = zipfile.ZipFile(io.BytesIO(res.content))
    root = "atronexus-messaging/"
    assert root + "workspace/fndbas/source/fndbas/database/CAtxMessageUtil-Cust.plsql" in files.namelist()
    address = files.read(root + "config/connect/RoutingAddress_C_ATX_MESSAGE_ADDR.xml").decode()
    assert "<REST_ROOT_END_POINT>http://localhost:3000/api/hooks/ifs/messages</REST_ROOT_END_POINT>" in address
