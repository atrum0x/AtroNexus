"""Recording and summing tool usage."""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.tools.catalog import TOOLS, Tool
from app.usage.models import UsageEvent

# Event kinds. "<tool>.<what>"; the success kind is the one that's billable.
CAPTURE_SENT = "capture.sent"
CAPTURE_FAILED = "capture.failed"


def record(
    db: Session,
    org_id: int,
    tool: str,
    kind: str,
    *,
    billable: bool,
    ref: str | None = None,
    quantity: int = 1,
) -> None:
    """Adds a usage event to the session; the caller commits it with the action it counts."""
    db.add(UsageEvent(organization_id=org_id, tool=tool, kind=kind, billable=billable, ref=ref, quantity=quantity))


def month_start(when: datetime) -> datetime:
    """The first moment of when's calendar month, in UTC (billing months are UTC)."""
    when = when.astimezone(timezone.utc)
    return when.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def previous_month_start(start: datetime) -> datetime:
    return (start.replace(year=start.year - 1, month=12) if start.month == 1 else start.replace(month=start.month - 1))


def next_month_start(start: datetime) -> datetime:
    return start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)


@dataclass
class ToolUsage:
    succeeded: int = 0  # billable events
    failed: int = 0  # everything else


def usage_by_tool(db: Session, org_id: int, start: datetime, end: datetime) -> dict[str, ToolUsage]:
    """Sums an organization's usage per tool for [start, end)."""
    rows = db.execute(
        select(UsageEvent.tool, UsageEvent.billable, func.coalesce(func.sum(UsageEvent.quantity), 0))
        .where(
            UsageEvent.organization_id == org_id,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by(UsageEvent.tool, UsageEvent.billable)
    ).all()
    result: dict[str, ToolUsage] = {}
    for tool, billable, total in rows:
        usage = result.setdefault(tool, ToolUsage())
        if billable:
            usage.succeeded += int(total)
        else:
            usage.failed += int(total)
    return result


@dataclass
class CostItem:
    tool: Tool
    usage_count: int
    usage_cost: Decimal

    @property
    def total(self) -> Decimal:
        return self.tool.monthly_price + self.usage_cost


def cost_items(enabled: set[str], usage: dict[str, ToolUsage]) -> list[CostItem]:
    """What a month costs: the monthly fee of each switched-on tool, plus billable
    usage at the tool's per-use price. Prices are the catalog's (placeholders for now)."""
    items = []
    for tool in TOOLS:
        if tool.code not in enabled:
            continue
        count = usage.get(tool.code, ToolUsage()).succeeded
        items.append(CostItem(tool, count, (tool.usage_price or Decimal(0)) * count))
    return items
