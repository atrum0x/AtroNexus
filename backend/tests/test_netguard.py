"""IFS connections can't point at internal networks (SSRF)."""

import httpx
import pytest

from app.config import get_settings
from app.ifs import client as ifs_client
from app.ifs.netguard import BlockedAddress, check_url
from tests.test_capture import make_connection

INTERNAL = [
    "127.0.0.1",  # loopback
    "10.1.2.3",  # private
    "172.16.0.5",  # private
    "192.168.1.10",  # private
    "169.254.169.254",  # link-local: the cloud metadata service
    "100.64.0.1",  # shared / CGNAT
    "0.0.0.0",  # unspecified
    "224.0.0.1",  # multicast
    "::1",  # IPv6 loopback
    "fd00::1",  # IPv6 unique local
    "fe80::1%eth0",  # IPv6 link-local with a zone
    "::ffff:10.0.0.1",  # IPv4-mapped private
]


@pytest.mark.parametrize("ip", INTERNAL)
def test_hosts_that_resolve_inward_are_blocked(fake_dns, ip):
    fake_dns["ifs.evil.example"] = [ip]
    with pytest.raises(BlockedAddress, match="internal network address"):
        check_url("https://ifs.evil.example/main")


def test_one_internal_answer_among_public_ones_is_enough_to_block(fake_dns):
    fake_dns["mixed.example"] = ["93.184.216.34", "10.0.0.1"]
    with pytest.raises(BlockedAddress):
        check_url("https://mixed.example")


def test_ip_literals_are_checked_too(fake_dns):
    fake_dns["169.254.169.254"] = ["169.254.169.254"]
    with pytest.raises(BlockedAddress):
        check_url("https://169.254.169.254/latest/meta-data")


def test_userinfo_doesnt_hide_the_real_host(fake_dns):
    fake_dns["10.0.0.1"] = ["10.0.0.1"]
    with pytest.raises(BlockedAddress):
        check_url("https://ifs.example.com@10.0.0.1/")


def test_only_https(fake_dns):
    for url in ("http://ifs.example.com", "ftp://ifs.example.com", "file:///etc/passwd"):
        with pytest.raises(BlockedAddress, match="https"):
            check_url(url)


def test_unknown_hosts_are_refused_with_a_clear_message(monkeypatch):
    from app.ifs import netguard

    def no_dns(host, port):
        raise OSError("not found")

    monkeypatch.setattr(netguard, "resolve", no_dns)
    with pytest.raises(BlockedAddress, match="Can't find"):
        check_url("https://nope.invalid")


def test_public_hosts_pass(fake_dns):
    fake_dns["ifs.customer.example"] = ["4.194.101.252", "2606:4700::6810:84e5"]
    check_url("https://ifs.customer.example:8443/main")


def test_the_development_switch_allows_private_addresses(fake_dns, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_private_ifs_urls", True)
    fake_dns["localhost"] = ["127.0.0.1"]
    check_url("http://localhost:8200")


# --- Where it's enforced ---


def test_saving_a_connection_with_an_internal_address_is_refused(client, auth_headers, fake_dns):
    fake_dns["metadata.evil.example"] = ["169.254.169.254"]
    body = {"name": "Evil", "base_url": "https://metadata.evil.example", "auth_type": "basic",
            "username": "u", "secret": "p"}
    res = client.post("/api/ifs-connections", json=body, headers=auth_headers)
    assert res.status_code == 422
    assert "internal network address" in res.json()["detail"]
    assert client.get("/api/ifs-connections", headers=auth_headers).json() == []


def test_an_internal_token_url_is_refused_too(client, auth_headers, fake_dns):
    fake_dns["kc.evil.example"] = ["10.0.0.5"]
    body = {"name": "Evil", "base_url": "https://ifs.example.com", "auth_type": "oauth2",
            "token_url": "https://kc.evil.example/token", "client_id": "c", "secret": "s"}
    assert client.post("/api/ifs-connections", json=body, headers=auth_headers).status_code == 422


def test_changing_an_address_to_an_internal_one_is_refused(client, auth_headers, fake_dns):
    conn = make_connection(client, auth_headers)
    fake_dns["inside.evil.example"] = ["192.168.0.1"]
    body = {"name": "x", "base_url": "https://inside.evil.example", "auth_type": "basic", "username": "u"}
    res = client.put(f"/api/ifs-connections/{conn['id']}", json=body, headers=auth_headers)
    assert res.status_code == 422


def test_a_name_that_later_resolves_inward_is_blocked_at_call_time(client, auth_headers, fake_dns):
    """DNS can change after saving; every call checks again and nothing is sent."""
    sent: list[httpx.Request] = []
    ifs_client.transport = httpx.MockTransport(lambda req: sent.append(req) or httpx.Response(200, json={}))
    try:
        fake_dns["ifs.example.com"] = ["93.184.216.34"]
        conn = make_connection(client, auth_headers, auth_type="basic", username="u", token_url=None,
                               client_id=None)
        fake_dns["ifs.example.com"] = ["10.0.0.1"]  # rebinding
        res = client.post(f"/api/ifs-connections/{conn['id']}/test", headers=auth_headers)
        assert res.json()["ok"] is False
        assert "internal network address" in res.json()["message"]
        assert sent == []
    finally:
        ifs_client.transport = None
