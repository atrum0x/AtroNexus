"""Calls to Meta's WhatsApp Cloud API (graph.facebook.com).

Every call goes through `MetaClient`, which takes the sender account to use.
Today that's AtroNexus's shared account; customers' own accounts come later
and use the same client.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings

# Tests replace this with an httpx.MockTransport.
transport: httpx.BaseTransport | None = None

TIMEOUT = 20.0


class MetaError(Exception):
    def __init__(self, message: str, status_code: int | None = None, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


@dataclass(frozen=True)
class SenderAccount:
    """The WhatsApp Business account and number that send for an organization."""

    kind: str  # "shared" (AtroNexus's number); "own" later
    waba_id: str
    phone_number_id: str
    access_token: str
    display_number: str | None = None


def _error_message(res: httpx.Response) -> MetaError:
    try:
        err = res.json().get("error") or {}
    except ValueError:
        err = {}
    details = (err.get("error_data") or {}).get("details")
    message = err.get("error_user_msg") or details or err.get("message") or f"Meta answered {res.status_code}."
    return MetaError(str(message)[:900], res.status_code, err.get("code"))


class MetaClient:
    def __init__(self, account: SenderAccount):
        self.account = account

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        base = get_settings().meta_graph_url.rstrip("/")
        try:
            with httpx.Client(transport=transport, timeout=TIMEOUT) as http:
                res = http.request(
                    method,
                    f"{base}/{path.lstrip('/')}",
                    headers={"Authorization": f"Bearer {self.account.access_token}"},
                    **kwargs,
                )
        except httpx.TimeoutException:
            raise MetaError("WhatsApp (Meta) didn't answer in time.") from None
        except httpx.HTTPError as exc:
            raise MetaError(f"Can't reach WhatsApp (Meta): {exc}") from None
        if res.status_code >= 400:
            raise _error_message(res)
        try:
            return res.json()
        except ValueError:
            return {}

    def send_template(self, to: str, name: str, language: str, components: list[dict[str, Any]]) -> str:
        """Sends a template message; returns Meta's message ID."""
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {"name": name, "language": {"code": language}},
        }
        if components:
            body["template"]["components"] = components
        data = self._request("POST", f"{self.account.phone_number_id}/messages", json=body)
        try:
            return str(data["messages"][0]["id"])
        except (KeyError, IndexError, TypeError):
            raise MetaError("WhatsApp (Meta) didn't return a message ID.") from None

    def create_template(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submits a template for review; returns {"id", "status", "category"}."""
        return self._request("POST", f"{self.account.waba_id}/message_templates", json=payload)

    def get_template(self, template_id: str) -> dict[str, Any]:
        return self._request("GET", template_id, params={"fields": "name,status,category,rejected_reason"})

    def delete_template(self, name: str) -> None:
        self._request("DELETE", f"{self.account.waba_id}/message_templates", params={"name": name})
