import json

import httpx
import pytest

from app.capture.template import render_body, validate_template
from app.ifs import client as ifs_client

IFS = "https://ifs.example.com"
ENDPOINT = "/main/ifsapplications/projection/v1/CaptureRequestHandling.svc/CaptureRequestSet(RequestId='{request_id}')"
TEMPLATE = json.dumps(
    {
        "CfStatus": "{status}",
        "CfLatitude": "{latitude}",
        "CfLongitude": "{longitude}",
        "CfNote": "From {ip} ({device})",
    }
)


class FakeIfs:
    """Plays IFS: a token endpoint plus one capture request record."""

    def __init__(self, known_ids=("REQ-1", "REQ-2"), patch_status=204):
        self.known_ids = set(known_ids)
        self.patch_status = patch_status
        self.calls: list[httpx.Request] = []
        self.token_calls = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.url.path == "/auth/token":
            self.token_calls += 1
            form = dict(x.split("=") for x in request.content.decode().split("&"))
            if form.get("client_secret") != "s3cret":
                return httpx.Response(401, json={"error": "invalid_client", "error_description": "Bad secret"})
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 300})

        if request.headers.get("Authorization") != "Bearer tok":
            return httpx.Response(401, json={"error": {"message": "Not signed in"}})

        path = request.url.path
        if path.endswith("CaptureRequestHandling.svc/"):
            return httpx.Response(200, json={"value": []})
        req_id = path.split("RequestId='")[-1].rstrip("')")
        if req_id not in self.known_ids:
            return httpx.Response(404, json={"error": {"message": "Not found"}})
        if request.method == "GET":
            return httpx.Response(200, headers={"ETag": 'W/"etag-1"'}, json={"RequestId": req_id})
        if request.method == "PATCH":
            if request.headers.get("If-Match") != 'W/"etag-1"':
                return httpx.Response(412, json={"error": {"message": "ETag mismatch"}})
            if self.patch_status >= 400:
                return httpx.Response(
                    self.patch_status, json={"error": {"message": "Location is too far from the site"}}
                )
            return httpx.Response(self.patch_status)
        return httpx.Response(405)

    def patches(self):
        return [c for c in self.calls if c.method == "PATCH"]


@pytest.fixture
def fake_ifs():
    fake = FakeIfs()
    ifs_client.transport = httpx.MockTransport(fake)
    ifs_client._tokens.clear()
    yield fake
    ifs_client.transport = None
    ifs_client._tokens.clear()


def make_connection(client, headers, **overrides):
    body = {
        "name": "Test IFS",
        "base_url": IFS,
        "auth_type": "oauth2",
        "token_url": f"{IFS}/auth/token",
        "client_id": "atronexus",
        "secret": "s3cret",
        **overrides,
    }
    res = client.post("/api/ifs-connections", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def make_target(client, headers, connection_id, **overrides):
    body = {
        "name": "Receipt location",
        "connection_id": connection_id,
        "endpoint_path": ENDPOINT,
        "http_method": "PATCH",
        "body_template": TEMPLATE,
        **overrides,
    }
    res = client.post("/api/capture/targets", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


CAPTURED = {
    "status": "captured",
    "latitude": 6.9271,
    "longitude": 79.8612,
    "accuracy": 12.34,
    "platform": "Windows",
    "screen": "1920x1080",
    "language": "en-GB",
}


@pytest.fixture
def target(client, auth_headers, fake_ifs):
    conn = make_connection(client, auth_headers)
    return make_target(client, auth_headers, conn["id"])


# --- Admin endpoints ---


def test_admin_endpoints_need_login(client):
    assert client.get("/api/ifs-connections").status_code == 401
    assert client.get("/api/capture/targets").status_code == 401
    assert client.get("/api/capture/captures").status_code == 401


def test_connection_secret_is_never_returned(client, auth_headers):
    conn = make_connection(client, auth_headers)
    listed = client.get("/api/ifs-connections", headers=auth_headers).json()
    for payload in (conn, listed[0]):
        assert "secret" not in payload and "secret_enc" not in payload
        assert "s3cret" not in json.dumps(payload)


def test_connection_secret_is_encrypted_at_rest(client, auth_headers):
    from app.db import SessionLocal
    from app.ifs.models import IfsConnection

    make_connection(client, auth_headers)
    with SessionLocal() as db:
        stored = db.query(IfsConnection).one().secret_enc
    assert "s3cret" not in stored


def test_update_without_secret_keeps_the_old_one(client, auth_headers, fake_ifs):
    conn = make_connection(client, auth_headers)
    body = {"name": "Renamed", "base_url": IFS, "auth_type": "oauth2",
            "token_url": f"{IFS}/auth/token", "client_id": "atronexus"}
    assert client.put(f"/api/ifs-connections/{conn['id']}", json=body, headers=auth_headers).status_code == 200
    res = client.post(f"/api/ifs-connections/{conn['id']}/test", headers=auth_headers).json()
    assert res["ok"], res


def test_create_connection_requires_secret(client, auth_headers):
    body = {"name": "x", "base_url": IFS, "auth_type": "oauth2",
            "token_url": f"{IFS}/auth/token", "client_id": "c"}
    assert client.post("/api/ifs-connections", json=body, headers=auth_headers).status_code == 422


def test_oauth2_needs_token_url(client, auth_headers):
    body = {"name": "x", "base_url": IFS, "auth_type": "oauth2", "client_id": "c", "secret": "s"}
    assert client.post("/api/ifs-connections", json=body, headers=auth_headers).status_code == 422


def test_test_connection_reports_bad_secret(client, auth_headers, fake_ifs):
    conn = make_connection(client, auth_headers, secret="wrong")
    res = client.post(f"/api/ifs-connections/{conn['id']}/test", headers=auth_headers).json()
    assert res == {"ok": False, "message": "Sign-in to IFS failed (401): Bad secret"}


def test_test_capture_target_reaches_projection(client, auth_headers, target):
    res = client.post(f"/api/capture/targets/{target['id']}/test", headers=auth_headers).json()
    assert res["ok"], res


def test_target_rejects_unknown_placeholder(client, auth_headers):
    conn = make_connection(client, auth_headers)
    res = client.post(
        "/api/capture/targets",
        json={"name": "x", "connection_id": conn["id"], "endpoint_path": ENDPOINT,
              "body_template": '{"A": "{lattitude}"}'},
        headers=auth_headers,
    )
    assert res.status_code == 422
    assert "lattitude" in res.text


def test_cannot_delete_connection_in_use(client, auth_headers, target):
    res = client.delete(f"/api/ifs-connections/{target['connection_id']}", headers=auth_headers)
    assert res.status_code == 409


# --- Public capture flow ---


def public_url(target, request_id="REQ-1"):
    return f"/api/public/capture/{target['public_id']}/{request_id}"


def test_capture_is_written_back_to_ifs(client, target, fake_ifs, auth_headers):
    info = client.get(public_url(target)).json()
    assert info == {"target_name": "Receipt location", "request_id": "REQ-1", "already_sent": False}

    res = client.post(public_url(target), json=CAPTURED, headers={"X-Forwarded-For": "203.0.113.9"})
    assert res.json() == {"ok": True, "message": "Saved to IFS."}

    [patch] = fake_ifs.patches()
    assert patch.url.path.endswith("CaptureRequestSet(RequestId='REQ-1')")
    assert json.loads(patch.content) == {
        "CfStatus": "Captured",
        "CfLatitude": 6.9271,
        "CfLongitude": 79.8612,
        "CfNote": "From testclient (Windows, 1920x1080, en-GB)",
    }

    log = client.get("/api/capture/captures", headers=auth_headers).json()
    assert log[0]["writeback_status"] == "sent"
    assert client.get(public_url(target)).json()["already_sent"] is True


def test_token_is_reused_between_captures(client, target, fake_ifs):
    client.post(public_url(target, "REQ-1"), json=CAPTURED)
    client.post(public_url(target, "REQ-2"), json=CAPTURED)
    assert fake_ifs.token_calls == 1


def test_second_capture_for_same_request_is_rejected(client, target, fake_ifs):
    client.post(public_url(target), json=CAPTURED)
    res = client.post(public_url(target), json=CAPTURED)
    assert res.status_code == 409
    assert len(fake_ifs.patches()) == 1


def test_denied_location_is_still_sent(client, target, fake_ifs):
    res = client.post(public_url(target), json={"status": "denied", "location_error": "User denied"})
    assert res.json()["ok"]
    body = json.loads(fake_ifs.patches()[0].content)
    assert body["CfStatus"] == "Denied"
    assert body["CfLatitude"] is None


def test_unknown_request_id_fails_without_patching(client, target, fake_ifs):
    res = client.post(public_url(target, "NOPE-9"), json=CAPTURED).json()
    assert res == {"ok": False, "message": "IFS has no capture request with this ID."}
    assert fake_ifs.patches() == []


def test_ifs_rejection_is_reported_and_can_be_retried(client, target, fake_ifs, auth_headers):
    fake_ifs.patch_status = 400
    res = client.post(public_url(target), json=CAPTURED).json()
    assert res == {"ok": False, "message": "IFS answered 400: Location is too far from the site"}
    log = client.get("/api/capture/captures", headers=auth_headers).json()
    assert log[0]["writeback_status"] == "failed"

    fake_ifs.patch_status = 204
    assert client.post(public_url(target), json=CAPTURED).json()["ok"]
    log = client.get("/api/capture/captures", headers=auth_headers).json()
    assert len(log) == 1 and log[0]["writeback_status"] == "sent"


@pytest.mark.parametrize("bad_id", ["REQ'1", "a b", "x" * 101, "REQ-1)/Other"])
def test_request_id_that_could_break_the_ifs_url_is_rejected(client, target, bad_id):
    assert client.post(public_url(target, bad_id), json=CAPTURED).status_code in (404, 422)


def test_disabled_or_unknown_target_link_is_invalid(client, auth_headers, target):
    assert client.get("/api/public/capture/doesnotexist/REQ-1").status_code == 404
    body = {**{k: target[k] for k in ("name", "connection_id", "endpoint_path", "http_method", "body_template")},
            "enabled": False}
    client.put(f"/api/capture/targets/{target['id']}", json=body, headers=auth_headers)
    assert client.get(public_url(target)).status_code == 404


def test_captured_without_coordinates_is_rejected(client, target):
    assert client.post(public_url(target), json={"status": "captured"}).status_code == 422


# --- Template ---


def test_render_keeps_types_for_whole_placeholders():
    out = render_body('{"a": "{latitude}", "b": ["{status}"], "c": "x{latitude}y", "d": 5}',
                      {"latitude": None, "status": "Captured"})
    assert out == {"a": None, "b": ["Captured"], "c": "xy", "d": 5}


def test_text_suffix_sends_numbers_as_strings():
    template = '{"lat": "{latitude:text}", "acc": "{accuracy:text}", "lon": "{longitude:text}", "s": "at {latitude:text}"}'
    validate_template(template)
    out = render_body(template, {"latitude": 6.9271, "accuracy": 12, "longitude": None})
    assert out == {"lat": "6.9271", "acc": "12", "lon": None, "s": "at 6.9271"}


def test_validate_template_rejects_unknown_placeholder_with_text_suffix():
    with pytest.raises(ValueError, match="nope"):
        validate_template('{"a": "{nope:text}"}')


def test_validate_template_rejects_non_object():
    with pytest.raises(ValueError):
        validate_template("[1, 2]")


def test_times_in_the_api_carry_a_utc_offset(client, target, fake_ifs, auth_headers):
    client.post(public_url(target), json=CAPTURED)
    [row] = client.get("/api/capture/captures", headers=auth_headers).json()
    assert row["captured_at"].endswith("Z") or row["captured_at"].endswith("+00:00")


def test_client_ip_from_the_frontend_is_used_only_with_the_key(client, target, fake_ifs, auth_headers, monkeypatch):
    from app.config import get_settings

    key = "k" * 40
    monkeypatch.setattr(get_settings(), "internal_api_key", key)
    with_key = {"X-Internal-Key": key}

    client.post(public_url(target, "REQ-1"), json=CAPTURED, headers={**with_key, "X-Client-IP": "203.0.113.9"})
    client.post(public_url(target, "REQ-2"), json=CAPTURED, headers={**with_key, "X-Client-IP": "not-an-ip"})
    log = client.get("/api/capture/captures", headers={**auth_headers, **with_key}).json()
    ips = {row["request_id"]: row["ip"] for row in log}
    assert ips == {"REQ-1": "203.0.113.9", "REQ-2": "testclient"}


def test_client_ip_header_is_ignored_from_untrusted_callers(client, target, fake_ifs, auth_headers):
    # No key configured, and the caller isn't on this machine.
    client.post(public_url(target), json=CAPTURED, headers={"X-Client-IP": "203.0.113.9"})
    [row] = client.get("/api/capture/captures", headers=auth_headers).json()
    assert row["ip"] == "testclient"
