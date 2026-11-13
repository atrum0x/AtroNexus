from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.deps import CurrentUser, DbSession, ManagerOnly, OrgId, get_current_user
from app.tools import service
from app.tools.catalog import BY_CODE, TOOLS, Tool

router = APIRouter(prefix="/api/tools", tags=["tools"], dependencies=[Depends(get_current_user)])


class ToolOut(BaseModel):
    code: str
    name: str
    description: str
    monthly_price: Decimal
    usage_price: Decimal | None
    usage_unit: str | None
    available: bool
    enabled: bool


class ToolSwitch(BaseModel):
    enabled: bool


def _out(tool: Tool, enabled: set[str]) -> ToolOut:
    return ToolOut(
        code=tool.code,
        name=tool.name,
        description=tool.description,
        monthly_price=tool.monthly_price,
        usage_price=tool.usage_price,
        usage_unit=tool.usage_unit,
        available=tool.available,
        enabled=tool.code in enabled,
    )


@router.get("", response_model=list[ToolOut])
def list_tools(db: DbSession, org_id: OrgId) -> list[ToolOut]:
    enabled = service.enabled_tools(db, org_id)
    return [_out(t, enabled) for t in TOOLS]


@router.put("/{code}", response_model=ToolOut, dependencies=[ManagerOnly])
def switch_tool(code: str, body: ToolSwitch, db: DbSession, org_id: OrgId, me: CurrentUser) -> ToolOut:
    tool = BY_CODE.get(code)
    if tool is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such tool")
    if body.enabled and not tool.available:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{tool.name} isn't available yet.")
    service.set_enabled(db, org_id, code, body.enabled, me)
    db.commit()
    return _out(tool, service.enabled_tools(db, org_id))
