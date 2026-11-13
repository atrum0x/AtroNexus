"""Builds the IFS request body from the admin's JSON template.

The template is a JSON object whose string values may contain {placeholders}.
A value that is exactly one placeholder, like "{latitude}", is replaced with
the typed value (a number, or null when missing). Placeholders inside longer
strings are replaced with text.
"""

import json
import re
from typing import Any

PLACEHOLDERS: dict[str, str] = {
    "request_id": "The request ID from the capture link",
    "status": "Captured, Denied or Unavailable",
    "latitude": "Latitude in degrees (number, null if not captured)",
    "longitude": "Longitude in degrees (number, null if not captured)",
    "accuracy": "Accuracy radius in metres (number, null if not captured)",
    "location_error": "Why there's no location, if there isn't one",
    "ip": "The user's IP address as seen by the server",
    "user_agent": "The browser's user agent string",
    "platform": "Operating system reported by the browser",
    "language": "Browser language, e.g. en-GB",
    "time_zone": "Browser time zone, e.g. Asia/Colombo",
    "screen": "Screen size, e.g. 1920x1080",
    "device": "Short summary: platform, screen and language",
    "captured_at": "When the capture happened (ISO 8601, UTC)",
}

DEFAULT_BODY_TEMPLATE = json.dumps(
    {
        "CfStatus": "{status}",
        "CfLatitude": "{latitude}",
        "CfLongitude": "{longitude}",
        "CfAccuracy": "{accuracy}",
        "CfIpAddress": "{ip}",
        "CfDevice": "{device}",
        "CfCapturedAt": "{captured_at}",
    },
    indent=2,
)

DEFAULT_ENDPOINT_PATH = (
    "/main/ifsapplications/projection/v1/CaptureRequestHandling.svc"
    "/CaptureRequestSet(RequestId='{request_id}')"
)

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def validate_template(text: str) -> None:
    """Raises ValueError with a readable message if the template is unusable."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Body template isn't valid JSON: {exc.msg} (line {exc.lineno}).") from exc
    if not isinstance(data, dict) or not data:
        raise ValueError("Body template must be a JSON object with at least one field.")
    unknown = sorted(_find_placeholders(data) - PLACEHOLDERS.keys())
    if unknown:
        raise ValueError(f"Unknown placeholder(s) in body template: {', '.join(unknown)}.")


def validate_endpoint_path(path: str) -> None:
    if not path.startswith("/"):
        raise ValueError("Endpoint path must start with /.")
    unknown = sorted(set(_PLACEHOLDER.findall(path)) - {"request_id"})
    if unknown:
        raise ValueError(f"Endpoint path can only use {{request_id}}, not: {', '.join(unknown)}.")


def render_body(template: str, values: dict[str, Any]) -> Any:
    return _render(json.loads(template), values)


def render_path(path: str, request_id: str) -> str:
    # request_id is checked against a strict pattern before it gets here, so
    # it can't break out of the OData key or add path segments.
    return path.replace("{request_id}", request_id)


def _render(node: Any, values: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        return {k: _render(v, values) for k, v in node.items()}
    if isinstance(node, list):
        return [_render(v, values) for v in node]
    if isinstance(node, str):
        whole = _PLACEHOLDER.fullmatch(node)
        if whole and whole.group(1) in values:
            return values[whole.group(1)]
        def as_text(m: re.Match[str]) -> str:
            key = m.group(1)
            if key not in values:
                return m.group(0)
            return "" if values[key] is None else str(values[key])

        return _PLACEHOLDER.sub(as_text, node)
    return node


def _find_placeholders(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set().union(*(_find_placeholders(v) for v in node.values())) if node else set()
    if isinstance(node, list):
        return set().union(*(_find_placeholders(v) for v in node)) if node else set()
    if isinstance(node, str):
        return set(_PLACEHOLDER.findall(node))
    return set()
