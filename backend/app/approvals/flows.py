"""The kinds of IFS approvals AtroNexus handles ("approval types").

Each organization picks the types it wants on the Approvals page. A type that
isn't `available` is a placeholder: it's listed as coming soon and can't be
switched on.

Adding a real type:
1. In the IFS package, add its functions to C_Atx_Approval_Util_API and its
   actions to the CAtxApprovalHandling projection, and put its event action(s)
   in `backend/ifs_package/approvals/flows/<folder>/`.
2. Fill in `keys`, `actions`, `reference` and `event_actions` here and set
   `available=True`. The hook, the email, the approval page, the log and the
   package download then work from this entry.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IfsActions:
    """Action names in the CAtxApprovalHandling projection."""

    status: str  # returns {"status": PENDING|SIGNED|NOT_YET|REJECTED, "summary": {...}}
    approve: str  # returns APPROVED, or SIGNED/NOT_YET/REJECTED
    reject: str  # returns REJECTED, or SIGNED/NOT_YET
    reject_reasons: str  # returns [{"id", "description"}]


@dataclass(frozen=True)
class EventAction:
    """One item of the IFS application configuration package."""

    name: str  # ITEMS_ROW/NAME, e.g. "901^EVENT_ID^LuName"
    filename: str  # file in flows/<folder>/, goes to Items/ in the package
    description: str


@dataclass(frozen=True)
class Flow:
    code: str  # the "kind" in IFS's message, stored on each request
    name: str  # plural, for the setup page: "Purchase requisition lines"
    noun: str  # singular, in sentences: "purchase requisition"
    description: str
    available: bool = False
    # (field in IFS's message, parameter name in the projection), in IFS key order.
    keys: tuple[tuple[str, str], ...] = ()
    # How the keys read to a person, e.g. "{0} line {1}".
    reference: str = ""
    actions: IfsActions | None = None
    folder: str = ""  # backend/ifs_package/approvals/flows/<folder>
    ifs_events: tuple[str, ...] = ()  # events the customer enables in IFS
    event_actions: tuple[EventAction, ...] = field(default_factory=tuple)

    def describe(self, keys: list[str]) -> str:
        """The record's reference, e.g. "R1001 line 1"."""
        try:
            return self.reference.format(*keys)
        except (IndexError, KeyError):
            return " · ".join(keys)

    def title(self, keys: list[str]) -> str:
        """e.g. "Purchase requisition R1001 line 1"."""
        return f"{self.noun[:1].upper()}{self.noun[1:]} {self.describe(keys)}"


PR_LINE = "PR_LINE"

FLOWS: tuple[Flow, ...] = (
    Flow(
        code=PR_LINE,
        name="Purchase requisition lines",
        noun="purchase requisition",
        description="Authorize requisition lines that wait on an authorization route.",
        available=True,
        keys=(("requisitionNo", "RequisitionNo"), ("lineNo", "LineNo"), ("releaseNo", "ReleaseNo")),
        reference="{0} line {1}",
        actions=IfsActions(
            status="GetPrLineStatus",
            approve="ApprovePrLine",
            reject="RejectPrLine",
            reject_reasons="GetRejectReasons",
        ),
        folder="pr_line",
        ifs_events=("PUR_REQ_LINE_TO_BE_AUTHORIZED",),
        event_actions=(
            EventAction(
                name="901^PUR_REQ_LINE_TO_BE_AUTHORIZED^PurchReqLineApproval",
                filename="CustomEventAction-PurchReqLineApproval-PUR_REQ_LINE_TO_BE_AUTHORIZED-901-EXECUTEONLINESQL.xml",
                description="AtroNexus: request purchase requisition line approval by email",
            ),
        ),
    ),
    # Placeholders: shown as coming soon until they're built.
    Flow(
        code="PURCHASE_ORDER",
        name="Purchase orders",
        noun="purchase order",
        description="Authorize purchase orders that wait on an authorization route.",
    ),
    Flow(
        code="PO_CHANGE_ORDER",
        name="Purchase order change orders",
        noun="purchase order change order",
        description="Authorize changes to purchase orders that were already released.",
    ),
    Flow(
        code="SUPPLIER_INVOICE",
        name="Supplier invoices",
        noun="supplier invoice",
        description="Authorize supplier invoices before they're posted.",
    ),
    Flow(
        code="EXPENSE_SHEET",
        name="Expense sheets",
        noun="expense sheet",
        description="Approve employees' expense sheets.",
    ),
    Flow(
        code="DOCUMENT_REVISION",
        name="Document revisions",
        noun="document revision",
        description="Approve document revisions on an approval route in Document Management.",
    ),
)

_BY_CODE = {f.code: f for f in FLOWS}


def get(code: str) -> Flow | None:
    return _BY_CODE.get(code)


def available() -> list[Flow]:
    return [f for f in FLOWS if f.available]
