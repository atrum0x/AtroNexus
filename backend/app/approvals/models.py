from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UtcDateTime
from app.ifs.models import IfsConnection
from app.links.models import SecureLink


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalSetup(Base):
    """An organization's approvals settings: which IFS connection, and the hook key IFS sends."""

    __tablename__ = "approval_setups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True)
    # The service user AtroNexus approves through (needs the IFS package and IMPERSONATE USER).
    connection_id: Mapped[int | None] = mapped_column(ForeignKey("ifs_connections.id"))
    # IFS sends "Authorization: Bearer <hook key>"; only its hash is stored.
    hook_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    hook_key_hint: Mapped[str | None] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # How long an approval link works (IFS also stops a token after 30 days).
    link_days: Mapped[int] = mapped_column(Integer, default=7)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now, onupdate=_now)

    connection: Mapped[IfsConnection | None] = relationship(lazy="joined")


# ApprovalRequest.status
SENT = "sent"  # emailed, waiting for a decision
APPROVED = "approved"
REJECTED = "rejected"
CLOSED = "closed"  # handled in IFS, or by someone else
EMAIL_FAILED = "email_failed"


class ApprovalRequest(Base):
    """One approval step for one person, as IFS sent it.

    A step with several possible approvers (a group, a substitute) becomes one
    row per person; the first decision closes the others.
    """

    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "kind", "requisition_no", "line_no", "release_no", "sequence_no", "fnd_user",
            name="uq_approval_requests_step_person",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # "PR_LINE"
    company: Mapped[str] = mapped_column(String(20))
    requisition_no: Mapped[str] = mapped_column(String(20))
    line_no: Mapped[str] = mapped_column(String(10))
    release_no: Mapped[str] = mapped_column(String(10))
    sequence_no: Mapped[int] = mapped_column(Integer)

    fnd_user: Mapped[str] = mapped_column(String(30))
    approver_name: Mapped[str] = mapped_column(String(200))
    approver_email: Mapped[str] = mapped_column(String(254))
    # The token IFS issued for this step and person, encrypted. AtroNexus only
    # passes it back; it can't make new ones.
    ifs_token_enc: Mapped[str] = mapped_column(String(500))
    issued_at: Mapped[int] = mapped_column(Integer)  # seconds since 1970, as IFS signed it
    summary_json: Mapped[str] = mapped_column(Text)  # what IFS sent, shown if IFS can't be reached

    status: Mapped[str] = mapped_column(String(20), default=SENT)
    link_id: Mapped[int | None] = mapped_column(ForeignKey("secure_links.id"))
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    reject_reason_id: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(2000))
    error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now, onupdate=_now)

    link: Mapped[SecureLink | None] = relationship(lazy="joined")
