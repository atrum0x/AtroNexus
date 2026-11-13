"""Rate limits on public capture links, and giving a capture page a new link."""

from app.capture import router as capture_router
from app.ratelimit import RateLimiter
from tests.conftest import add_user, login_headers
from tests.test_capture import CAPTURED, fake_ifs, make_connection, make_target, public_url, target  # noqa: F401


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


# --- The limiter itself ---


def test_limiter_allows_up_to_the_limit_then_says_how_long_to_wait():
    clock = FakeClock()
    limiter = RateLimiter(limit=3, window=60, clock=clock)
    assert [limiter.hit("a") for _ in range(3)] == [None, None, None]
    wait = limiter.hit("a")
    assert wait is not None and 0 < wait <= 60
    assert limiter.hit("b") is None  # other keys are separate


def test_limiter_window_slides():
    clock = FakeClock()
    limiter = RateLimiter(limit=2, window=60, clock=clock)
    limiter.hit("a")
    clock.now += 30
    limiter.hit("a")
    assert limiter.hit("a") is not None
    clock.now += 31  # the first hit is now older than the window
    assert limiter.hit("a") is None


# --- On the capture endpoints ---


def test_opening_a_link_too_often_is_slowed_down(client, target, monkeypatch):
    monkeypatch.setattr(capture_router, "view_limiter", RateLimiter(limit=3, window=60))
    codes = [client.get(public_url(target)).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    res = client.get(public_url(target))
    assert int(res.headers["Retry-After"]) >= 1
    assert "Too many attempts" in res.json()["detail"]


def test_submitting_too_often_is_slowed_down_before_ifs_is_called(client, target, fake_ifs, monkeypatch):
    monkeypatch.setattr(capture_router, "submit_limiter_minute", RateLimiter(limit=2, window=60))
    codes = [client.post(public_url(target, f"REQ-{n}"), json=CAPTURED).status_code for n in (1, 2, 3)]
    assert codes[:2] != [429, 429] and codes[2] == 429
    calls_before = len(fake_ifs.calls)
    assert client.post(public_url(target, "REQ-9"), json=CAPTURED).status_code == 429
    assert len(fake_ifs.calls) == calls_before  # refused requests never reach IFS


def test_each_visitor_has_their_own_limit(client, target, monkeypatch):
    from app.config import get_settings

    key = "k" * 40
    monkeypatch.setattr(get_settings(), "internal_api_key", key)
    monkeypatch.setattr(capture_router, "view_limiter", RateLimiter(limit=1, window=60))

    def view(ip):
        return client.get(public_url(target), headers={"X-Internal-Key": key, "X-Client-IP": ip}).status_code

    assert [view("203.0.113.1"), view("203.0.113.1"), view("203.0.113.2")] == [200, 429, 200]


def test_a_capture_page_has_an_overall_submission_limit(client, target, fake_ifs, monkeypatch):
    from app.config import get_settings

    key = "k" * 40
    monkeypatch.setattr(get_settings(), "internal_api_key", key)
    monkeypatch.setattr(capture_router, "page_submit_limiter", RateLimiter(limit=2, window=3600))
    codes = [
        client.post(public_url(target, f"REQ-{n}"), json=CAPTURED,
                    headers={"X-Internal-Key": key, "X-Client-IP": f"203.0.113.{n}"}).status_code
        for n in (1, 2, 3)  # three different visitors
    ]
    assert codes[2] == 429


# --- A new link ---


def test_new_link_kills_the_old_one(client, target, auth_headers):
    res = client.post(f"/api/capture/targets/{target['id']}/new-link", headers=auth_headers)
    assert res.status_code == 200
    renewed = res.json()
    assert renewed["public_id"] != target["public_id"] and len(renewed["public_id"]) == 16
    assert client.get(public_url(target)).status_code == 404
    assert client.get(public_url(renewed)).status_code == 200


def test_captures_survive_a_new_link(client, target, auth_headers, fake_ifs):
    client.post(public_url(target), json=CAPTURED)
    client.post(f"/api/capture/targets/{target['id']}/new-link", headers=auth_headers)
    assert len(client.get("/api/capture/captures", headers=auth_headers).json()) == 1


def test_only_owners_and_admins_of_that_org_can_renew(client, other_org_headers, auth_headers, fake_ifs):
    conn = make_connection(client, other_org_headers)
    target = make_target(client, other_org_headers, conn["id"])
    assert client.post(f"/api/capture/targets/{target['id']}/new-link", headers=auth_headers).status_code == 404
    add_user("mo", "Other Co", role="member")
    member = login_headers(client, "mo", "pass1234")
    assert client.post(f"/api/capture/targets/{target['id']}/new-link", headers=member).status_code == 403
