"""Messaging hub (tool 2): WhatsApp templates, scenarios IFS triggers, and the messages sent."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UtcDateTime


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MessagingSetup(Base):
    """An organization's messaging settings and the hook key IFS sends."""

    __tablename__ = "messaging_setups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True)
    # IFS sends "Authorization: Bearer <hook key>"; only its hash is stored.
    hook_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    hook_key_hint: Mapped[str | None] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # Turns local numbers into international ones: with "94", 0771234567 becomes 94771234567.
    default_country_code: Mapped[str | None] = mapped_column(String(4))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now, onupdate=_now)


# MessageTemplate.status
DRAFT = "draft"  # saved, not (successfully) submitted to Meta yet
PENDING = "pending"  # Meta is reviewing it
APPROVED = "approved"
REJECTED = "rejected"
PAUSED = "paused"  # Meta paused it (quality); sends fail until it's back
DISABLED = "disabled"


class MessageTemplate(Base):
    """A WhatsApp message template. Meta must approve it before it can be sent.

    Variables are numbered: {{1}}, {{2}}, ... in the body, at most {{1}} in the
    header, and {{1}} at the end of a URL button's address.
    """

    __tablename__ = "message_templates"
    __table_args__ = (UniqueConstraint("organization_id", "name", "language", name="uq_message_templates_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))  # what the customer calls it: lowercase, digits, _
    language: Mapped[str] = mapped_column(String(10))  # e.g. "en", "en_US", "si"
    category: Mapped[str] = mapped_column(String(20))  # UTILITY or MARKETING
    header_text: Mapped[str | None] = mapped_column(String(60))
    body_text: Mapped[str] = mapped_column(String(1024))
    footer_text: Mapped[str | None] = mapped_column(String(60))
    # [{"type": "URL", "text": ..., "url": ...} | {"type": "QUICK_REPLY", "text": ...}]
    buttons_json: Mapped[str] = mapped_column(Text, default="[]")
    # Example values Meta reviews: {"header": [...], "body": [...], "buttons": {"0": "..."}}
    examples_json: Mapped[str] = mapped_column(Text, default="{}")

    # Where it lives in Meta. In the shared account every organization's
    # templates sit side by side, so the Meta name gets an organization prefix.
    waba_id: Mapped[str | None] = mapped_column(String(40))
    meta_name: Mapped[str] = mapped_column(String(120))
    meta_template_id: Mapped[str | None] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(20), default=DRAFT)
    status_reason: Mapped[str | None] = mapped_column(String(1000))
    submitted_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now, onupdate=_now)


class MessageScenario(Base):
    """A named situation IFS triggers (e.g. ORDER_SHIPPED): which template, to
    whom, and which IFS values fill its variables.

    The mappings are text with {field} placeholders for values IFS sends,
    e.g. recipient "{phone}", body ["{customerName}", "Order {orderNo}"].
    """

    __tablename__ = "message_scenarios"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_message_scenarios_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))  # what IFS passes, e.g. ORDER_SHIPPED
    name: Mapped[str] = mapped_column(String(100))
    template_id: Mapped[int] = mapped_column(ForeignKey("message_templates.id"))
    recipient: Mapped[str] = mapped_column(String(200))
    header_param: Mapped[str | None] = mapped_column(String(500))
    body_params_json: Mapped[str] = mapped_column(Text, default="[]")
    button_params_json: Mapped[str] = mapped_column(Text, default="{}")  # {"0": "{orderNo}"}
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now, onupdate=_now)

    template: Mapped[MessageTemplate] = relationship(lazy="joined")


# Message.status, in the order they normally happen.
SENDING = "sending"
SENT = "sent"  # Meta accepted it
DELIVERED = "delivered"
READ = "read"
FAILED = "failed"
STATUS_ORDER = {SENDING: 0, SENT: 1, DELIVERED: 2, READ: 3}

# Message.source
FROM_IFS = "ifs"
FROM_TEST = "test"


class Message(Base):
    """One WhatsApp message, from IFS or a test send."""

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("organization_id", "external_id", name="uq_messages_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("message_scenarios.id", ondelete="SET NULL"))
    scenario_code: Mapped[str | None] = mapped_column(String(40))  # kept if the scenario is deleted
    template_name: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(10))
    # IFS's own ID for the message, so a resend from IFS isn't sent twice.
    external_id: Mapped[str | None] = mapped_column(String(100))
    to_phone: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)  # the body with values filled in, for the log
    params_json: Mapped[str] = mapped_column(Text, default="{}")  # what IFS sent

    status: Mapped[str] = mapped_column(String(20), default=SENDING)
    meta_message_id: Mapped[str | None] = mapped_column(String(100), index=True)
    error: Mapped[str | None] = mapped_column(String(1000))
    sent_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    read_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now, onupdate=_now)
