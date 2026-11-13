"""Which tools an organization has switched on."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import DbSession, OrgId
from app.models import OrganizationTool, ToolEvent, User
from app.tools.catalog import BY_CODE


def enabled_tools(db: Session, org_id: int) -> set[str]:
    return set(
        db.scalars(
            select(OrganizationTool.tool).where(
                OrganizationTool.organization_id == org_id, OrganizationTool.enabled
            )
        ).all()
    )


def is_enabled(db: Session, org_id: int, tool: str) -> bool:
    return tool in enabled_tools(db, org_id)


def set_enabled(db: Session, org_id: int, tool: str, enabled: bool, user: User | None) -> OrganizationTool:
    """Switches a tool on or off and logs it. Switching to the current state changes nothing."""
    row = db.scalar(
        select(OrganizationTool).where(OrganizationTool.organization_id == org_id, OrganizationTool.tool == tool)
    )
    if row is None:
        row = OrganizationTool(organization_id=org_id, tool=tool, enabled=False)
        db.add(row)
    if row.enabled == enabled:
        return row
    row.enabled = enabled
    if enabled:
        row.enabled_at = datetime.now(timezone.utc)
    db.add(ToolEvent(organization_id=org_id, tool=tool, enabled=enabled, user_id=user.id if user else None))
    return row


def require_tool(tool: str):
    """Dependency for a tool's admin endpoints: 403 while the organization has it off."""
    name = BY_CODE[tool].name

    def check(db: DbSession, org_id: OrgId) -> None:
        if not is_enabled(db, org_id, tool):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"{name} is switched off for your organization. An owner or admin can switch it on in Tools.",
            )

    return Depends(check)
