"""Sends email. The first piece of the "message channels" building block.

EMAIL_BACKEND=console (default) writes each email to the log instead of sending
it, so everything works before a sending domain exists. EMAIL_BACKEND=resend
sends through Resend's HTTP API.

Callers schedule send_email as a FastAPI background task, so a slow or failing
email provider never fails the request that triggered it.
"""

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings

log = logging.getLogger("atronexus.email")

RESEND_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    text: str


# Every email sent, newest last. Tests read it; it's capped so a long-running
# console-mode server doesn't grow it forever.
outbox: list[Email] = []
_OUTBOX_LIMIT = 100


def send_email(email: Email) -> None:
    outbox.append(email)
    del outbox[:-_OUTBOX_LIMIT]

    settings = get_settings()
    if settings.email_backend == "resend":
        _send_resend(email)
    else:
        log.warning("Email (not sent, EMAIL_BACKEND=console) to %s: %s\n%s", email.to, email.subject, email.text)


def _send_resend(email: Email) -> None:
    settings = get_settings()
    if not settings.resend_api_key:
        log.error("EMAIL_BACKEND=resend but RESEND_API_KEY is empty; email to %s not sent", email.to)
        return
    try:
        res = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.email_from, "to": [email.to], "subject": email.subject, "text": email.text},
            timeout=15,
        )
        res.raise_for_status()
    except httpx.HTTPError as exc:
        detail = exc.response.text[:300] if isinstance(exc, httpx.HTTPStatusError) else str(exc)
        log.error("Sending email to %s failed: %s", email.to, detail)
