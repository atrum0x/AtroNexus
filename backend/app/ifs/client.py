"""Calls the IFS REST API as a connection's service user.

Every tool goes through IfsClient, so authentication, token caching and error
handling live in one place.
"""

import ssl
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import truststore

from app.config import get_settings
from app.crypto import decrypt
from app.ifs.models import IfsConnection
from app.ifs.netguard import BlockedAddress, check_url

# Tests replace this with an httpx.MockTransport.
transport: httpx.BaseTransport | None = None

# OAuth2 tokens per connection: id -> (token, expires_at, connection version).
_tokens: dict[int, tuple[str, float, str]] = {}
_tokens_lock = threading.Lock()


@lru_cache
def _tls_context() -> ssl.SSLContext:
    """Verifies IFS certificates against the operating system's trust store.

    Python's bundled CA list (certifi) fails on servers that don't send their
    intermediate certificate, which happens on real IFS environments. Windows
    and macOS fetch a missing intermediate the way browsers do, and the OS
    store also has any company CAs that IT installed. Verification stays on.
    """
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


class IfsError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class IfsResponse:
    status_code: int
    headers: httpx.Headers
    body: Any


class IfsClient:
    def __init__(self, conn: IfsConnection):
        self.conn = conn

    def _http(self) -> httpx.Client:
        return httpx.Client(
            timeout=get_settings().ifs_timeout_seconds,
            transport=transport,
            follow_redirects=False,
            verify=_tls_context(),
        )

    def _auth_headers(self) -> dict[str, str]:
        if self.conn.auth_type == "basic":
            return {}
        return {"Authorization": f"Bearer {self._oauth2_token()}"}

    def _basic_auth(self) -> tuple[str, str] | None:
        if self.conn.auth_type == "basic":
            return (self.conn.username or "", decrypt(self.conn.secret_enc))
        return None

    def _oauth2_token(self) -> str:
        version = self.conn.updated_at.isoformat() if self.conn.updated_at else ""
        with _tokens_lock:
            cached = _tokens.get(self.conn.id)
        if cached and cached[2] == version and cached[1] > time.time() + 30:
            return cached[0]

        _guard(self.conn.token_url or "")
        try:
            with self._http() as http:
                res = http.post(
                    self.conn.token_url or "",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.conn.client_id or "",
                        "client_secret": decrypt(self.conn.secret_enc),
                    },
                )
        except httpx.HTTPError as exc:
            raise IfsError(f"Can't reach the token URL: {exc}") from exc

        if res.status_code != 200:
            raise IfsError(
                f"Sign-in to IFS failed ({res.status_code}): {_error_text(res)}", res.status_code
            )
        data = res.json()
        token = data.get("access_token")
        if not token:
            raise IfsError("The token URL answered without an access_token.")
        expires_at = time.time() + float(data.get("expires_in", 300))
        with _tokens_lock:
            _tokens[self.conn.id] = (token, expires_at, version)
        return token

    def authenticate(self) -> None:
        """Checks the credentials. For OAuth2 this fetches a token."""
        if self.conn.auth_type == "oauth2":
            self._oauth2_token()

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> IfsResponse:
        url = self.conn.base_url.rstrip("/") + path
        _guard(url)
        all_headers = {"Accept": "application/json", **self._auth_headers(), **(headers or {})}
        try:
            with self._http() as http:
                res = http.request(
                    method, url, json=json, headers=all_headers, auth=self._basic_auth()
                )
        except httpx.HTTPError as exc:
            raise IfsError(f"Can't reach IFS: {exc}") from exc

        if res.status_code >= 400:
            raise IfsError(f"IFS answered {res.status_code}: {_error_text(res)}", res.status_code)
        body: Any = None
        if res.content:
            try:
                body = res.json()
            except ValueError:
                body = res.text
        return IfsResponse(res.status_code, res.headers, body)


def _guard(url: str) -> None:
    """Checked before every call, not just when saving: DNS answers can change."""
    try:
        check_url(url)
    except BlockedAddress as exc:
        raise IfsError(str(exc)) from exc


def _error_text(res: httpx.Response) -> str:
    """Pulls the message out of an IFS (OData) or OAuth2 error response."""
    try:
        data = res.json()
    except ValueError:
        return (res.text or res.reason_phrase)[:300]
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
        if data.get("error_description"):
            return str(data["error_description"])[:300]
        if isinstance(err, str):
            return err[:300]
    return str(data)[:300]


def forget_token(connection_id: int) -> None:
    with _tokens_lock:
        _tokens.pop(connection_id, None)
