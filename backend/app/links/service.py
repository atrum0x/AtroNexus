"""Creating and resolving secure links."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.links.models import SecureLink
from app.security import hash_link_token, new_link_token


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create(
    db: Session, org_id: int, purpose: str, recipient_email: str, lifetime: timedelta
) -> tuple[SecureLink, str]:
    """Returns the link and the token for its URL (shown once, never stored)."""
    token, token_hash = new_link_token()
    link = SecureLink(
        organization_id=org_id,
        purpose=purpose,
        token_hash=token_hash,
        recipient_email=recipient_email,
        expires_at=_now() + lifetime,
    )
    db.add(link)
    db.flush()
    return link, token


def find(db: Session, token: str, purpose: str) -> SecureLink | None:
    """The link behind a token, whatever its state; None if it doesn't exist."""
    link = db.scalar(select(SecureLink).where(SecureLink.token_hash == hash_link_token(token)))
    if link is None or link.purpose != purpose:
        return None
    return link


def state(link: SecureLink) -> str:
    """"open", "used", "revoked" or "expired"."""
    if link.revoked_at is not None:
        return "revoked"
    if link.used_at is not None:
        return "used"
    if link.expires_at <= _now():
        return "expired"
    return "open"


def mark_opened(link: SecureLink) -> None:
    link.opened_at = link.opened_at or _now()


def mark_used(link: SecureLink) -> None:
    link.used_at = _now()


def revoke(link: SecureLink) -> None:
    if link.revoked_at is None and link.used_at is None:
        link.revoked_at = _now()
