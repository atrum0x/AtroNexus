"""Lets only the AtroNexus frontend call this API, and carries the browser's IP.

In production the API has its own public address (Northflank), and the
frontend runs on Vercel. The frontend sends a shared secret in X-Internal-Key
with every request. Requests without it are refused, so nobody can call the API
directly. Because the secret proves the request came from our frontend, the
X-Client-IP header it sends (the browser's address) can be trusted.
"""

import ipaddress
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.config import get_settings

KEY_HEADER = "x-internal-key"
CLIENT_IP_HEADER = "x-client-ip"
OPEN_PATHS = {"/api/health"}  # for the hosting platform's health check


def _has_valid_key(request: Request) -> bool:
    expected = get_settings().internal_api_key
    sent = request.headers.get(KEY_HEADER, "")
    return bool(expected) and secrets.compare_digest(sent.encode(), expected.encode())


class InternalKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if get_settings().internal_api_key and request.url.path not in OPEN_PATHS:
            if not _has_valid_key(request):
                # 403, not 401: the frontend treats 401 as "session expired".
                return JSONResponse({"detail": "Forbidden"}, status_code=403)
        return await call_next(request)


def client_ip(request: Request) -> str | None:
    """The browser's IP address, as passed on by the frontend."""
    direct = request.client.host if request.client else None
    trusted = _has_valid_key(request) or (
        # Local development without a key: trust the Next.js server on this machine.
        not get_settings().internal_api_key and _is_loopback(direct)
    )
    forwarded = request.headers.get(CLIENT_IP_HEADER, "").strip()
    if trusted and forwarded and _is_ip(forwarded):
        return forwarded
    return direct


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _is_loopback(value: str | None) -> bool:
    return value is not None and _is_ip(value) and ipaddress.ip_address(value).is_loopback
