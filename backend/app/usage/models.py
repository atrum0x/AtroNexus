from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UtcDateTime


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UsageEvent(Base):
    """One counted use of a tool. Monthly usage, and later per-use billing, are sums of these.

    Rows are only ever added, never changed, so a month's numbers can be
    recalculated at any time.
    """

    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_events_org_created", "organization_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    # A code from app.tools.catalog.
    tool: Mapped[str] = mapped_column(String(40))
    # What happened, e.g. "capture.sent" or "capture.failed".
    kind: Mapped[str] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    # Counts towards the tool's per-use price. Failures never do: a customer
    # isn't charged for something that didn't reach IFS.
    billable: Mapped[bool] = mapped_column(Boolean)
    # What it was about, for tracing a number back, e.g. "capture:42".
    ref: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
