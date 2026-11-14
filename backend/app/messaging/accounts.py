"""Which WhatsApp account sends for an organization.

Version 1: every organization sends from AtroNexus's shared number (the
WHATSAPP_* settings). The plan is for each customer to connect their own
WhatsApp Business number (Meta Embedded Signup); that returns a
SenderAccount(kind="own") from here, and nothing else needs to change.
"""

from sqlalchemy.orm import Session

from app.config import get_settings
from app.messaging.meta import SenderAccount

SHARED = "shared"
NOT_CONNECTED = "WhatsApp isn't connected on this AtroNexus yet."


def shared_account() -> SenderAccount | None:
    s = get_settings()
    if not (s.whatsapp_business_account_id and s.whatsapp_phone_number_id and s.whatsapp_access_token):
        return None
    return SenderAccount(
        kind=SHARED,
        waba_id=s.whatsapp_business_account_id,
        phone_number_id=s.whatsapp_phone_number_id,
        access_token=s.whatsapp_access_token,
        display_number=s.whatsapp_display_number,
    )


def account_for(db: Session, org_id: int) -> SenderAccount | None:  # noqa: ARG001 (db: for own accounts later)
    return shared_account()


def meta_template_name(account_kind: str, org_id: int, name: str) -> str:
    """Template names are unique per WhatsApp account; in the shared one, prefix the organization."""
    return f"atx{org_id}_{name}" if account_kind == SHARED else name
