"""The platform admin's view of every customer organization.

Only users with is_platform_admin may use it. Everyone else gets 404, so the
admin surface doesn't reveal itself.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.capture.models import Capture, CaptureTarget
from app.deps import CurrentUser, DbSession
from app.ifs.models import IfsConnection
from app.models import ORG_ACTIVE, ORG_SUSPENDED, Organization, OrganizationTool, ToolEvent, User
from app.tools.catalog import BY_CODE
from app.usage import service as usage
from app.usage.models import UsageEvent


def require_platform_admin(user: CurrentUser) -> User:
    if not user.is_platform_admin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return user


router = APIRouter(prefix="/api/platform", tags=["platform"], dependencies=[Depends(require_platform_admin)])


# --- Schemas ---


class OrgRow(BaseModel):
    id: int
    name: str
    status: str
    created_at: datetime
    owner: str | None
    members: int
    tools: list[str]
    usage_succeeded: int
    usage_failed: int
    estimated_revenue: Decimal
    last_activity: datetime | None


class PlatformSummary(BaseModel):
    organizations: int
    active: int
    suspended: int
    users: int
    usage_succeeded: int
    usage_failed: int
    estimated_revenue: Decimal


class PlatformOverview(BaseModel):
    month_start: datetime
    summary: PlatformSummary
    organizations: list[OrgRow]


class MemberRow(BaseModel):
    id: int
    name: str | None
    email: str | None
    username: str | None
    role: str
    email_verified: bool
    is_platform_admin: bool
    created_at: datetime


class ToolRow(BaseModel):
    tool: str
    name: str
    enabled: bool
    enabled_at: datetime | None
    succeeded: int
    failed: int
    last_month_succeeded: int


class ToolHistoryRow(BaseModel):
    tool: str
    name: str
    enabled: bool
    by: str | None
    at: datetime


class ErrorRow(BaseModel):
    title: str
    message: str
    at: datetime


class OrgDetail(BaseModel):
    id: int
    name: str
    status: str
    status_changed_at: datetime | None
    status_reason: str | None
    created_at: datetime
    is_platform_org: bool
    members: list[MemberRow]
    tools: list[ToolRow]
    tool_history: list[ToolHistoryRow]
    connections: int
    capture_pages: int
    estimated_revenue: Decimal
    recent_errors: list[ErrorRow]


class StatusChange(BaseModel):
    status: Literal["active", "suspended"]
    reason: str | None = Field(default=None, max_length=500)


# --- Helpers ---


def _month() -> tuple[datetime, datetime, datetime]:
    start = usage.month_start(datetime.now(timezone.utc))
    return usage.previous_month_start(start), start, usage.next_month_start(start)


def _label(user: User | None) -> str | None:
    if user is None:
        return None
    return user.name or user.email or user.username


def _enabled_by_org(db: DbSession) -> dict[int, set[str]]:
    result: dict[int, set[str]] = {}
    for org_id, tool in db.execute(
        select(OrganizationTool.organization_id, OrganizationTool.tool).where(OrganizationTool.enabled)
    ):
        result.setdefault(org_id, set()).add(tool)
    return result


def _usage_by_org(db: DbSession, start: datetime, end: datetime) -> dict[int, dict[str, usage.ToolUsage]]:
    result: dict[int, dict[str, usage.ToolUsage]] = {}
    rows = db.execute(
        select(
            UsageEvent.organization_id,
            UsageEvent.tool,
            UsageEvent.billable,
            func.coalesce(func.sum(UsageEvent.quantity), 0),
        )
        .where(UsageEvent.created_at >= start, UsageEvent.created_at < end)
        .group_by(UsageEvent.organization_id, UsageEvent.tool, UsageEvent.billable)
    )
    for org_id, tool, billable, total in rows:
        tool_usage = result.setdefault(org_id, {}).setdefault(tool, usage.ToolUsage())
        if billable:
            tool_usage.succeeded += int(total)
        else:
            tool_usage.failed += int(total)
    return result


def _revenue(enabled: set[str], org_usage: dict[str, usage.ToolUsage]) -> Decimal:
    return sum((item.total for item in usage.cost_items(enabled, org_usage)), Decimal(0))


def _get_org(db: DbSession, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")
    return org


# --- Endpoints ---


@router.get("/organizations", response_model=PlatformOverview)
def list_organizations(db: DbSession) -> PlatformOverview:
    _, start, end = _month()
    orgs = db.scalars(select(Organization).order_by(Organization.created_at.desc())).all()
    enabled = _enabled_by_org(db)
    month_usage = _usage_by_org(db, start, end)

    members = dict(
        db.execute(select(User.organization_id, func.count()).group_by(User.organization_id)).all()
    )
    last_activity = dict(
        db.execute(
            select(UsageEvent.organization_id, func.max(UsageEvent.created_at)).group_by(UsageEvent.organization_id)
        ).all()
    )
    # The first owner (by sign-up time) of each organization.
    owners: dict[int, User] = {}
    for user in db.scalars(select(User).where(User.role == "owner").order_by(User.created_at)):
        owners.setdefault(user.organization_id, user)

    rows = []
    for org in orgs:
        org_enabled = enabled.get(org.id, set())
        org_usage = month_usage.get(org.id, {})
        activity = last_activity.get(org.id)
        rows.append(
            OrgRow(
                id=org.id,
                name=org.name,
                status=org.status,
                created_at=org.created_at,
                owner=_label(owners.get(org.id)),
                members=members.get(org.id, 0),
                tools=sorted(org_enabled),
                usage_succeeded=sum(u.succeeded for u in org_usage.values()),
                usage_failed=sum(u.failed for u in org_usage.values()),
                estimated_revenue=_revenue(org_enabled, org_usage) if org.status == ORG_ACTIVE else Decimal(0),
                # SQLite returns the max() as text; only use real datetimes.
                last_activity=activity if isinstance(activity, datetime) else None,
            )
        )

    summary = PlatformSummary(
        organizations=len(rows),
        active=sum(1 for r in rows if r.status == ORG_ACTIVE),
        suspended=sum(1 for r in rows if r.status == ORG_SUSPENDED),
        users=sum(members.values()),
        usage_succeeded=sum(r.usage_succeeded for r in rows),
        usage_failed=sum(r.usage_failed for r in rows),
        estimated_revenue=sum((r.estimated_revenue for r in rows), Decimal(0)),
    )
    return PlatformOverview(month_start=start, summary=summary, organizations=rows)


@router.get("/organizations/{org_id}", response_model=OrgDetail)
def get_organization(org_id: int, db: DbSession, me: CurrentUser) -> OrgDetail:
    org = _get_org(db, org_id)
    last_start, start, end = _month()
    this_month = usage.usage_by_tool(db, org.id, start, end)
    last_month = usage.usage_by_tool(db, org.id, last_start, start)
    tool_rows = db.scalars(select(OrganizationTool).where(OrganizationTool.organization_id == org.id)).all()
    state = {t.tool: t for t in tool_rows}
    enabled = {t.tool for t in tool_rows if t.enabled}

    members = db.scalars(select(User).where(User.organization_id == org.id).order_by(User.created_at)).all()
    history = db.execute(
        select(ToolEvent, User)
        .outerjoin(User, User.id == ToolEvent.user_id)
        .where(ToolEvent.organization_id == org.id)
        .order_by(ToolEvent.created_at.desc(), ToolEvent.id.desc())
        .limit(20)
    ).all()
    failed = db.scalars(
        select(Capture)
        .join(Capture.target)
        .where(CaptureTarget.organization_id == org.id, Capture.writeback_status == "failed")
        .order_by(Capture.captured_at.desc())
        .limit(5)
    ).all()

    tools = [
        ToolRow(
            tool=code,
            name=BY_CODE[code].name if code in BY_CODE else code,
            enabled=code in enabled,
            enabled_at=state[code].enabled_at if code in state else None,
            succeeded=this_month.get(code, usage.ToolUsage()).succeeded,
            failed=this_month.get(code, usage.ToolUsage()).failed,
            last_month_succeeded=last_month.get(code, usage.ToolUsage()).succeeded,
        )
        for code in sorted(set(state) | set(this_month) | set(last_month))
    ]

    return OrgDetail(
        id=org.id,
        name=org.name,
        status=org.status,
        status_changed_at=org.status_changed_at,
        status_reason=org.status_reason,
        created_at=org.created_at,
        is_platform_org=org.id == me.organization_id,
        members=[
            MemberRow(
                id=u.id,
                name=u.name,
                email=u.email,
                username=u.username,
                role=u.role,
                email_verified=u.email_verified_at is not None,
                is_platform_admin=u.is_platform_admin,
                created_at=u.created_at,
            )
            for u in members
        ],
        tools=tools,
        tool_history=[
            ToolHistoryRow(
                tool=event.tool,
                name=BY_CODE[event.tool].name if event.tool in BY_CODE else event.tool,
                enabled=event.enabled,
                by=_label(user),
                at=event.created_at,
            )
            for event, user in history
        ],
        connections=db.scalar(
            select(func.count()).select_from(IfsConnection).where(IfsConnection.organization_id == org.id)
        )
        or 0,
        capture_pages=db.scalar(
            select(func.count()).select_from(CaptureTarget).where(CaptureTarget.organization_id == org.id)
        )
        or 0,
        estimated_revenue=_revenue(enabled, this_month) if org.status == ORG_ACTIVE else Decimal(0),
        recent_errors=[
            ErrorRow(
                title=f"{c.target.name} · request {c.request_id}",
                message=c.writeback_error or "IFS didn't accept the capture.",
                at=c.captured_at,
            )
            for c in failed
        ],
    )


@router.put("/organizations/{org_id}/status", response_model=OrgDetail)
def set_organization_status(org_id: int, body: StatusChange, db: DbSession, me: CurrentUser) -> OrgDetail:
    """Suspends or reactivates a customer. Suspended: nobody can sign in, sessions stop
    working, and public links answer 404. Nothing is deleted."""
    org = _get_org(db, org_id)
    if org.id == me.organization_id and body.status == ORG_SUSPENDED:
        raise HTTPException(status.HTTP_409_CONFLICT, "You can't suspend the platform's own organization.")
    if org.status != body.status:
        org.status = body.status
        org.status_changed_at = datetime.now(timezone.utc)
        org.status_reason = (body.reason or "").strip() or None
        db.commit()
    return get_organization(org.id, db, me)
