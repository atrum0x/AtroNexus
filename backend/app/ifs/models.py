from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UtcDateTime


def _now() -> datetime:
    return datetime.now(timezone.utc)


class IfsConnection(Base):
    """One IFS environment and the service user the tools act as."""

    __tablename__ = "ifs_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    # "oauth2" (client credentials, the IFS Cloud default) or "basic".
    auth_type: Mapped[str] = mapped_column(String(20))
    token_url: Mapped[str | None] = mapped_column(String(500))
    client_id: Mapped[str | None] = mapped_column(String(200))
    username: Mapped[str | None] = mapped_column(String(200))
    # Client secret (oauth2) or password (basic), encrypted with app.crypto.
    secret_enc: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=_now, onupdate=_now
    )
