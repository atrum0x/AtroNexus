import json
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.approvals import flows, ifs_api, package, service
from app.approvals.models import SENT, ApprovalRequest, ApprovalSetup
from app.config import get_settings
from app.deps import DbSession, ManagerOnly, OrgId, VerifiedEmail, get_current_user
from app.email.sender import send_email
from app.ifs.client import IfsError
from app.ifs.router import get_org_connection
from app.ifs.schemas import CheckResult
from app.internal import client_ip
from app.links import service as links
from app.models import ORG_ACTIVE, Organization
from app.ratelimit import RateLimiter, enforce
from app.tools.catalog import APPROVALS
from app.tools.service import is_enabled, require_tool

HOOK_PATH = "/api/hooks/ifs/approvals"

# --- Schemas ---


class SetupOut(BaseModel):
    connection_id: int | None
    connection_name: str | None
    enabled: bool
    link_days: int
    hook_url: str
    has_hook_key: bool
    hook_key_hint: str | None


class SetupIn(BaseModel):
    connection_id: int | None = None
    enabled: bool = False
    link_days: int = Field(default=7, ge=1, le=30)


class HookKeyOut(BaseModel):
    hook_key: str


class FlowOut(BaseModel):
    """One approval type, and whether this organization uses it."""

    code: str
    name: str
    description: str
    available: bool  # False: a placeholder, coming soon
    enabled: bool
    ifs_events: list[str]


class FlowIn(BaseModel):
    enabled: bool


class RequestOut(BaseModel):
    id: int
    kind: str
    kind_name: str
    reference: str  # e.g. "R1001 line 1"
    sequence_no: int
    item: str | None
    line_total: str | None
    approver_name: str
    approver_email: str
    status: str
    link_state: str | None
    opened_at: datetime | None
    decided_at: datetime | None
    error: str | None
    created_at: datetime


class ApprovalView(BaseModel):
    """What the approval page shows."""

    link_state: str  # open, used, expired, revoked
    decision: str  # sent, approved, rejected, closed
    ifs_status: str | None  # PENDING, SIGNED, NOT_YET, REJECTED (live from IFS, when reachable)
    live: bool  # False: IFS couldn't be reached, summary is what IFS sent
    organization: str
    approver_name: str
    kind: str
    title: str  # e.g. "Purchase requisition R1001 line 1"
    summary: dict[str, Any]
    message: str | None = None


class RejectReason(BaseModel):
    id: str
    description: str


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    reason_id: str | None = Field(default=None, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class DecisionOut(BaseModel):
    result: str
    message: str


# --- Helpers ---


def _hook_url() -> str:
    return get_settings().app_url.rstrip("/") + HOOK_PATH


def _setup(db: DbSession, org_id: int) -> ApprovalSetup:
    setup = db.scalar(select(ApprovalSetup).where(ApprovalSetup.organization_id == org_id))
    if setup is None:
        setup = ApprovalSetup(organization_id=org_id)
        db.add(setup)
        db.flush()
    return setup


def _setup_out(setup: ApprovalSetup) -> SetupOut:
    return SetupOut(
        connection_id=setup.connection_id,
        connection_name=setup.connection.name if setup.connection else None,
        enabled=setup.enabled,
        link_days=setup.link_days,
        hook_url=_hook_url(),
        has_hook_key=setup.hook_key_hash is not None,
        hook_key_hint=setup.hook_key_hint,
    )


def _flows_out(db: DbSession, org_id: int) -> list[FlowOut]:
    on = service.enabled_flows(db, org_id)
    return [
        FlowOut(
            code=f.code,
            name=f.name,
            description=f.description,
            available=f.available,
            enabled=f.code in on,
            ifs_events=list(f.ifs_events),
        )
        for f in flows.FLOWS
    ]


def _kind_name(kind: str) -> str:
    flow = flows.get(kind)
    return flow.name if flow else kind


def _reference(r: ApprovalRequest) -> str:
    flow = flows.get(r.kind)
    return flow.describe(r.keys) if flow else " · ".join(r.keys)


# --- Admin ---

router = APIRouter(
    prefix="/api/approvals",
    tags=["approvals"],
    dependencies=[Depends(get_current_user), require_tool(APPROVALS)],
)


@router.get("/setup", response_model=SetupOut)
def get_approval_setup(db: DbSession, org_id: OrgId) -> SetupOut:
    setup = _setup(db, org_id)
    db.commit()
    return _setup_out(setup)


@router.put("/setup", response_model=SetupOut, dependencies=[ManagerOnly])
def update_approval_setup(body: SetupIn, db: DbSession, org_id: OrgId) -> SetupOut:
    setup = _setup(db, org_id)
    if body.connection_id is not None and get_org_connection(db, org_id, body.connection_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick an existing IFS connection.")
    if body.enabled and (body.connection_id is None or setup.hook_key_hash is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick an IFS connection and create a hook key before switching on."
        )
    setup.connection_id = body.connection_id
    setup.enabled = body.enabled
    setup.link_days = body.link_days
    db.commit()
    db.refresh(setup)
    return _setup_out(setup)


@router.get("/flows", response_model=list[FlowOut])
def list_approval_flows(db: DbSession, org_id: OrgId) -> list[FlowOut]:
    """Every approval type, with the ones this organization uses switched on."""
    return _flows_out(db, org_id)


@router.put("/flows/{code}", response_model=list[FlowOut], dependencies=[ManagerOnly])
def update_approval_flow(code: str, body: FlowIn, db: DbSession, org_id: OrgId) -> list[FlowOut]:
    flow = flows.get(code)
    if flow is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown approval type.")
    if body.enabled and not flow.available:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{flow.name} aren't available yet.")
    service.set_flow(db, org_id, code, body.enabled)
    db.commit()
    return _flows_out(db, org_id)


@router.post("/setup/hook-key", response_model=HookKeyOut, dependencies=[ManagerOnly])
def create_hook_key(db: DbSession, org_id: OrgId) -> HookKeyOut:
    """A new key for the IFS routing address. The old one stops working at once."""
    setup = _setup(db, org_id)
    key = service.new_hook_key(setup)
    db.commit()
    return HookKeyOut(hook_key=key)


@router.post("/setup/check", response_model=CheckResult, dependencies=[ManagerOnly, VerifiedEmail])
def check_approval_package(db: DbSession, org_id: OrgId) -> CheckResult:
    """Checks that the IFS package is deployed and the service user may use it."""
    setup = _setup(db, org_id)
    if setup.connection is None:
        return CheckResult(ok=False, message="Pick an IFS connection first.")
    try:
        ifs_api.check_package(setup.connection)
    except IfsError as exc:
        if exc.status_code == 404:
            return CheckResult(
                ok=False, message="IFS doesn't have the AtroNexus package (CAtxApprovalHandling). Deploy it first."
            )
        if exc.status_code == 403:
            return CheckResult(
                ok=False, message="The service user may not use CAtxApprovalHandling. Grant it in a permission set."
            )
        return CheckResult(ok=False, message=exc.message)
    return CheckResult(ok=True, message="IFS has the AtroNexus package, and the service user can use it.")


@router.get(
    "/package",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}, "description": "The IFS package as a zip"}},
)
def download_approval_package(db: DbSession, org_id: OrgId) -> Response:
    """The IFS package for the approval types switched on, with the routing address pointing at this AtroNexus."""
    chosen = [f for f in flows.FLOWS if f.code in service.enabled_flows(db, org_id)]
    if not chosen:
        raise HTTPException(status.HTTP_409_CONFLICT, "Switch on at least one approval type first.")
    return Response(
        content=package.build_zip(_hook_url(), chosen),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="atronexus-approvals-ifs-package.zip"'},
    )


@router.get("/requests", response_model=list[RequestOut])
def list_approval_requests(
    db: DbSession, org_id: OrgId, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[RequestOut]:
    service.expire_stale_links(db, org_id)
    db.commit()
    rows = db.scalars(
        select(ApprovalRequest)
        .where(ApprovalRequest.organization_id == org_id)
        .order_by(ApprovalRequest.created_at.desc())
        .limit(limit)
    ).all()
    out = []
    for r in rows:
        summary = json.loads(r.summary_json or "{}")
        total = service._money(summary.get("lineTotal"), summary.get("currency")) or None
        out.append(
            RequestOut(
                id=r.id,
                kind=r.kind,
                kind_name=_kind_name(r.kind),
                reference=_reference(r),
                sequence_no=r.sequence_no,
                item=summary.get("description") or summary.get("partNo"),
                line_total=total,
                approver_name=r.approver_name,
                approver_email=r.approver_email,
                status=r.status,
                link_state=links.state(r.link) if r.link else None,
                opened_at=r.link.opened_at if r.link else None,
                decided_at=r.decided_at,
                error=r.error,
                created_at=r.created_at,
            )
        )
    return out


# --- The hook IFS calls (through the frontend, which adds the internal key) ---

hook_router = APIRouter(tags=["approvals-hook"])
hook_limiter = RateLimiter(limit=600, window=3600)


@hook_router.post(HOOK_PATH)
def receive_approval_request(
    message: service.HookMessage,
    db: DbSession,
    background: BackgroundTasks,
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    key = (authorization or "").removeprefix("Bearer ").strip()
    setup = service.setup_for_hook_key(db, key) if key else None
    if setup is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown hook key.")
    enforce(hook_limiter, f"setup:{setup.id}", "Too many approval requests. Try again later.")
    org = db.get(Organization, setup.organization_id)
    if org is None or org.status != ORG_ACTIVE or not is_enabled(db, setup.organization_id, APPROVALS):
        raise HTTPException(status.HTTP_409_CONFLICT, "Approvals are switched off for this organization in AtroNexus.")
    if not setup.enabled or setup.connection is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Approvals aren't switched on in AtroNexus yet.")
    flow = flows.get(message.kind)
    if message.version != 1 or flow is None or not flow.available:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported message version or kind.")
    if flow.code not in service.enabled_flows(db, setup.organization_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"{flow.name} are switched off in AtroNexus.")
    try:
        key = service.object_key(flow, message)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    sent = service.receive(db, setup, message, key)
    db.commit()
    for request, token in sent:
        background.add_task(send_email, service.approval_email(request, token, setup.link_days))
    return {"received": len(sent)}


# --- The approval page (public, through the one-time link) ---

public_router = APIRouter(prefix="/api/public/approvals", tags=["approvals-public"])
LinkToken = Annotated[str, Path(min_length=20, max_length=100)]
view_limiter = RateLimiter(limit=60, window=60)
decide_limiter = RateLimiter(limit=10, window=60)
LIMITERS = (hook_limiter, view_limiter, decide_limiter)
NOT_VALID = "This approval link isn't valid. If you got a newer email about the same approval, use the link in that one."


def _visitor(request: Request) -> str:
    return client_ip(request) or "unknown"


def _resolve(db: DbSession, token: str) -> tuple[ApprovalRequest, ApprovalSetup, Any, Organization]:
    found = service.find_request_by_link(db, token)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_VALID)
    request, link = found
    org = db.get(Organization, request.organization_id)
    setup = db.scalar(select(ApprovalSetup).where(ApprovalSetup.organization_id == request.organization_id))
    if (
        org is None
        or org.status != ORG_ACTIVE
        or setup is None
        or not setup.enabled
        or setup.connection is None
        or not is_enabled(db, request.organization_id, APPROVALS)
        or request.kind not in service.enabled_flows(db, request.organization_id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_VALID)
    return request, setup, link, org


@public_router.get("/{token}", response_model=ApprovalView)
def get_approval(token: LinkToken, request: Request, db: DbSession) -> ApprovalView:
    enforce(view_limiter, _visitor(request), "Too many attempts. Wait a minute and try again.")
    approval, setup, link, org = _resolve(db, token)
    view = ApprovalView(
        link_state=links.state(link),
        decision=approval.status,
        ifs_status=None,
        live=False,
        organization=org.name,
        approver_name=approval.approver_name,
        kind=approval.kind,
        title=service.title(approval),
        summary=json.loads(approval.summary_json or "{}"),
    )
    if view.link_state != "open" or approval.status != SENT:
        return view

    links.mark_opened(link)
    try:
        live = ifs_api.step_status(setup.connection, approval)
        view.ifs_status = live.status
        view.summary = live.summary or view.summary
        view.live = True
    except IfsError as exc:
        view.message = f"Couldn't read the latest from IFS ({exc.message}). Showing what IFS sent earlier."
    db.commit()
    return view


@public_router.get("/{token}/reject-reasons", response_model=list[RejectReason])
def get_approval_reject_reasons(token: LinkToken, request: Request, db: DbSession) -> list[RejectReason]:
    enforce(view_limiter, _visitor(request), "Too many attempts. Wait a minute and try again.")
    approval, setup, link, _ = _resolve(db, token)
    if links.state(link) != "open":
        raise HTTPException(status.HTTP_409_CONFLICT, "This link can't be used any more.")
    try:
        return [RejectReason(**r) for r in ifs_api.reject_reasons(setup.connection, approval)]
    except IfsError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Couldn't read reject reasons from IFS: {exc.message}") from None


DECISION_MESSAGES = {
    "APPROVED": "Approved. IFS has recorded your authorization.",
    "REJECTED": "Rejected. IFS has recorded your rejection.",
    "SIGNED": "Someone already authorized this step in IFS. Nothing was changed.",
    "NOT_YET": "This step isn't ready for you yet: an earlier authorization is still open.",
}


@public_router.post("/{token}/decide", response_model=DecisionOut)
def decide_approval(token: LinkToken, body: DecisionIn, request: Request, db: DbSession) -> DecisionOut:
    enforce(decide_limiter, _visitor(request), "Too many attempts. Wait a minute and try again.")
    approval, setup, link, _ = _resolve(db, token)
    if links.state(link) != "open" or approval.status != SENT:
        raise HTTPException(status.HTTP_409_CONFLICT, "This approval was already handled. You can close this page.")
    if body.decision == "reject" and not body.reason_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a reason for rejecting.")
    try:
        result = service.decide(db, setup, approval, link, body.decision, body.reason_id, body.note)
    except IfsError as exc:
        service.record_failure(db, approval, exc.message)
        db.commit()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"IFS didn't accept it: {exc.message}") from None
    db.commit()
    if result == "REJECTED" and body.decision == "approve":
        return DecisionOut(result=result, message="This was already rejected. Nothing was changed.")
    return DecisionOut(result=result, message=DECISION_MESSAGES.get(result, result))
