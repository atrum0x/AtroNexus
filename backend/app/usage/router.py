"""The organization's overview: usage, recent errors, estimated cost, setup checklist."""

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.capture.models import Capture, CaptureTarget
from app.deps import CurrentUser, DbSession, OrgId, get_current_user
from app.ifs.models import IfsConnection
from app.models import Invitation, User
from app.tools.catalog import CAPTURE, TOOLS
from app.tools.service import enabled_tools
from app.usage import service

router = APIRouter(prefix="/api/overview", tags=["overview"], dependencies=[Depends(get_current_user)])

RECENT_ERRORS = 5


class ToolUsageOut(BaseModel):
    tool: str
    name: str
    enabled: bool
    succeeded: int
    failed: int
    last_month_succeeded: int


class RecentError(BaseModel):
    tool: str
    title: str
    message: str
    at: datetime
    link: str  # a frontend path


class CostLine(BaseModel):
    tool: str
    name: str
    monthly_fee: Decimal
    usage_count: int
    usage_price: Decimal | None
    usage_unit: str | None
    usage_cost: Decimal
    total: Decimal


class CostEstimate(BaseModel):
    lines: list[CostLine]
    total: Decimal


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool
    link: str


class Overview(BaseModel):
    month_start: datetime
    usage: list[ToolUsageOut]
    recent_errors: list[RecentError]
    # Only for owners and admins.
    estimate: CostEstimate | None
    checklist: list[ChecklistItem]


@router.get("", response_model=Overview)
def get_overview(db: DbSession, org_id: OrgId, me: CurrentUser) -> Overview:
    now = datetime.now(timezone.utc)
    start = service.month_start(now)
    last_start = service.previous_month_start(start)
    this_month = service.usage_by_tool(db, org_id, start, service.next_month_start(start))
    last_month = service.usage_by_tool(db, org_id, last_start, start)
    enabled = enabled_tools(db, org_id)

    # Tools that are on, plus any that were used this month and then switched off.
    shown = [t for t in TOOLS if t.code in enabled or t.code in this_month]
    usage = [
        ToolUsageOut(
            tool=t.code,
            name=t.name,
            enabled=t.code in enabled,
            succeeded=this_month.get(t.code, service.ToolUsage()).succeeded,
            failed=this_month.get(t.code, service.ToolUsage()).failed,
            last_month_succeeded=last_month.get(t.code, service.ToolUsage()).succeeded,
        )
        for t in shown
    ]

    estimate = None
    if me.role in ("owner", "admin"):
        lines = [
            CostLine(
                tool=item.tool.code,
                name=item.tool.name,
                monthly_fee=item.tool.monthly_price,
                usage_count=item.usage_count,
                usage_price=item.tool.usage_price,
                usage_unit=item.tool.usage_unit,
                usage_cost=item.usage_cost,
                total=item.total,
            )
            for item in service.cost_items(enabled, this_month)
        ]
        estimate = CostEstimate(lines=lines, total=sum((line.total for line in lines), Decimal(0)))

    return Overview(
        month_start=start,
        usage=usage,
        recent_errors=_recent_errors(db, org_id),
        estimate=estimate,
        checklist=_checklist(db, org_id, me, enabled),
    )


def _recent_errors(db: DbSession, org_id: int) -> list[RecentError]:
    failed = db.scalars(
        select(Capture)
        .join(Capture.target)
        .where(CaptureTarget.organization_id == org_id, Capture.writeback_status == "failed")
        .order_by(Capture.captured_at.desc())
        .limit(RECENT_ERRORS)
    ).all()
    return [
        RecentError(
            tool=CAPTURE,
            title=f"{c.target.name} · request {c.request_id}",
            message=c.writeback_error or "IFS didn't accept the capture.",
            at=c.captured_at,
            link=f"/capture/{c.target_id}",
        )
        for c in failed
    ]


def _count(db: DbSession, query) -> int:
    return db.scalar(select(func.count()).select_from(query.subquery())) or 0


def _checklist(db: DbSession, org_id: int, me: User, enabled: set[str]) -> list[ChecklistItem]:
    has_connection = _count(db, select(IfsConnection.id).where(IfsConnection.organization_id == org_id)) > 0
    has_capture_page = _count(db, select(CaptureTarget.id).where(CaptureTarget.organization_id == org_id)) > 0
    team_size = _count(db, select(User.id).where(User.organization_id == org_id))
    invited = _count(db, select(Invitation.id).where(Invitation.organization_id == org_id))
    items = [
        ChecklistItem(key="verify_email", label="Confirm your email address", done=me.email_verified_at is not None,
                      link="/"),
        ChecklistItem(key="tool", label="Switch on a tool", done=bool(enabled), link="/tools"),
        ChecklistItem(key="connection", label="Add an IFS connection", done=has_connection, link="/connections/new"),
    ]
    if CAPTURE in enabled:
        items.append(
            ChecklistItem(key="capture_page", label="Create a capture page", done=has_capture_page,
                          link="/capture/new")
        )
    items.append(ChecklistItem(key="team", label="Invite your team", done=team_size > 1 or invited > 0, link="/team"))
    return items

