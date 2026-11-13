import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UtcDateTime
from app.ifs.models import IfsConnection


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _public_id() -> str:
    return secrets.token_urlsafe(12)


class CaptureTarget(Base):
    """A capture page setup: which IFS connection to use and where to write the result."""

    __tablename__ = "capture_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Goes in the capture link. Random so links can't be guessed by counting.
    public_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, default=_public_id)
    name: Mapped[str] = mapped_column(String(100))
    connection_id: Mapped[int] = mapped_column(ForeignKey("ifs_connections.id"))
    # Path under the connection's base URL. May contain {request_id}.
    endpoint_path: Mapped[str] = mapped_column(String(1000))
    # PATCH updates an existing capture request; POST creates a record.
    http_method: Mapped[str] = mapped_column(String(10), default="PATCH")
    # JSON object with {placeholders}; see app.capture.template.
    body_template: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(), default=_now, onupdate=_now
    )

    connection: Mapped[IfsConnection] = relationship(lazy="joined")


class Capture(Base):
    """One capture from the page, and whether it reached IFS."""

    __tablename__ = "captures"
    __table_args__ = (UniqueConstraint("target_id", "request_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_id: Mapped[int] = mapped_column(ForeignKey("capture_targets.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))

    # "captured", "denied" (user refused) or "unavailable" (no fix / not supported).
    status: Mapped[str] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float)
    location_error: Mapped[str | None] = mapped_column(String(500))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    platform: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str | None] = mapped_column(String(50))
    time_zone: Mapped[str | None] = mapped_column(String(100))
    screen: Mapped[str | None] = mapped_column(String(50))
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)

    # "pending", "sent" or "failed".
    writeback_status: Mapped[str] = mapped_column(String(20), default="pending")
    writeback_error: Mapped[str | None] = mapped_column(String(1000))
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    target: Mapped[CaptureTarget] = relationship(lazy="joined")
