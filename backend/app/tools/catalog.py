"""The tools AtroNexus sells, and their prices.

Prices are PLACEHOLDERS until real pricing is decided. They're shown to
customers but nothing is charged yet. Billing (later) will read the
tool_events log for when each tool was on, and the usage records for
per-use charges.
"""

from dataclasses import dataclass
from decimal import Decimal

CAPTURE = "capture"
APPROVALS = "approvals"


@dataclass(frozen=True)
class Tool:
    code: str
    name: str
    description: str
    monthly_price: Decimal  # USD per organization per month
    # Per-use price on top of the monthly fee, for tools with a real cost per use.
    usage_price: Decimal | None = None
    usage_unit: str | None = None  # e.g. "message"
    # False until the tool is built: shown as "Coming soon", can't be switched on.
    available: bool = False


TOOLS: tuple[Tool, ...] = (
    Tool(
        CAPTURE,
        "Capture page",
        "Opened from a button in IFS. Reads the user's location, IP address and device, and writes them to the IFS record.",
        Decimal("29"),
        available=True,
    ),
    Tool(
        "messaging",
        "Messaging hub",
        "Send WhatsApp and SMS messages from IFS events and commands.",
        Decimal("49"),
        usage_price=Decimal("0.02"),
        usage_unit="message",
    ),
    Tool(
        APPROVALS,
        "Approve from email",
        "Approvers get an email and approve or reject purchase requisition lines without signing in to IFS. IFS still records the real approver. Needs the AtroNexus IFS package.",
        Decimal("39"),
        available=True,
    ),
    Tool(
        "email_in",
        "Email in, record out",
        "Turn incoming emails into IFS records, with attachments.",
        Decimal("29"),
    ),
    Tool(
        "guest_links",
        "Guest links and forms",
        "Let people without an IFS login view one item or submit a form through a secure link.",
        Decimal("49"),
    ),
    Tool(
        "documents",
        "SharePoint and OneDrive documents",
        "Link IFS documents to files in Microsoft 365.",
        Decimal("39"),
    ),
    Tool(
        "change_tracker",
        "Configuration change tracker",
        "An audit trail of configuration changes in IFS: who changed what, and when.",
        Decimal("59"),
    ),
)

BY_CODE: dict[str, Tool] = {t.code: t for t in TOOLS}
