from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UtcDateTime


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SecureLink(Base):
    """A link sent to one person about one item: the "secure links" building block.

    Only a SHA-256 hash of the token is stored. A link works until it expires,
    is revoked, or is used; opening it doesn't use it up, acting on it does.
    """

    __tablename__ = "secure_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    # What the link is for, e.g. "approval". A link only resolves for its purpose.
    purpose: Mapped[str] = mapped_column(String(40))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    recipient_email: Mapped[str] = mapped_column(String(254))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    opened_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
