"""Approvals: taking requests from IFS, emailing approvers, recording decisions."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.approvals import ifs_api
from app.approvals.models import (
    APPROVED,
    CLOSED,
    REJECTED,
    SENT,
    ApprovalRequest,
    ApprovalSetup,
)
from app.config import get_settings
from app.crypto import encrypt
from app.email.sender import Email
from app.links import service as links
from app.links.models import SecureLink
from app.security import hash_link_token, new_link_token
from app.tools.catalog import APPROVALS
from app.usage import service as usage

LINK_PURPOSE = "approval"


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- The message from IFS (contract version 1, see ifs/approvals/README.md) ---


class HookApprover(BaseModel):
    fndUser: str = Field(min_length=1, max_length=30)
    authorizeId: str | None = Field(default=None, max_length=30)
    name: str = Field(default="", max_length=200)
    email: str = Field(min_length=3, max_length=254)
    token: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class HookMessage(BaseModel):
    version: int
    kind: str
    company: str = Field(max_length=20)
    requisitionNo: str = Field(min_length=1, max_length=20)
    lineNo: str = Field(min_length=1, max_length=10)
    releaseNo: str = Field(min_length=1, max_length=10)
    sequenceNo: int
    issuedAt: int
    approvers: list[HookApprover] = Field(max_length=200)
    summary: dict[str, Any] = {}


# --- Hook keys ---


def new_hook_key(setup: ApprovalSetup) -> str:
    """Gives the setup a new hook key and returns it (shown once; only its hash is kept)."""
    key, key_hash = new_link_token()
    setup.hook_key_hash = key_hash
    setup.hook_key_hint = key[-4:]
    return key


def setup_for_hook_key(db: Session, key: str) -> ApprovalSetup | None:
    return db.scalar(select(ApprovalSetup).where(ApprovalSetup.hook_key_hash == hash_link_token(key)))


# --- Taking a request from IFS ---


def receive(db: Session, setup: ApprovalSetup, message: HookMessage) -> list[tuple[ApprovalRequest, str]]:
    """Creates or refreshes one request per approver and gives each a new link.

    Returns (request, link token) for every approver who should get an email.
    IFS sends the same step again when it's resent or re-routed: the newest
    token wins and the old link stops working. Decided steps are left alone.
    """
    out = []
    lifetime = timedelta(days=setup.link_days)
    for approver in message.approvers:
        request = db.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.organization_id == setup.organization_id,
                ApprovalRequest.kind == message.kind,
                ApprovalRequest.requisition_no == message.requisitionNo,
                ApprovalRequest.line_no == message.lineNo,
                ApprovalRequest.release_no == message.releaseNo,
                ApprovalRequest.sequence_no == message.sequenceNo,
                ApprovalRequest.fnd_user == approver.fndUser.upper(),
            )
        )
        if request is not None and request.status in (APPROVED, REJECTED):
            continue
        if request is None:
            request = ApprovalRequest(
                organization_id=setup.organization_id,
                kind=message.kind,
                requisition_no=message.requisitionNo,
                line_no=message.lineNo,
                release_no=message.releaseNo,
                sequence_no=message.sequenceNo,
                fnd_user=approver.fndUser.upper(),
            )
            db.add(request)
        elif request.link is not None:
            links.revoke(request.link)
        request.company = message.company
        request.approver_name = approver.name or approver.fndUser
        request.approver_email = approver.email.strip().lower()
        request.ifs_token_enc = encrypt(approver.token)
        request.issued_at = message.issuedAt
        request.summary_json = json.dumps(message.summary)[:20000]
        request.status = SENT
        request.error = None
        link, token = links.create(db, setup.organization_id, LINK_PURPOSE, request.approver_email, lifetime)
        request.link = link
        out.append((request, token))
    db.flush()
    return out


# --- Emails ---


def _money(amount: Any, currency: Any) -> str:
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return f"{value:,.2f} {currency or ''}".strip()


def summary_lines(summary: dict[str, Any]) -> list[str]:
    lines = []
    what = summary.get("description") or summary.get("partNo")
    if summary.get("partNo") and summary.get("description"):
        what = f"{summary['partNo']} · {summary['description']}"
    if what:
        lines.append(f"Item: {what}")
    if summary.get("quantity") is not None:
        lines.append(f"Quantity: {summary['quantity']} {summary.get('unit') or ''}".rstrip())
    total = _money(summary.get("lineTotal"), summary.get("currency"))
    if total:
        lines.append(f"Line total: {total}")
    if summary.get("supplierName") or summary.get("supplierId"):
        lines.append(f"Supplier: {summary.get('supplierName') or summary.get('supplierId')}")
    if summary.get("wantedReceiptDate"):
        lines.append(f"Wanted by: {summary['wantedReceiptDate']}")
    if summary.get("requisitioner"):
        lines.append(f"Requested by: {summary['requisitioner']}")
    return lines


def approval_email(request: ApprovalRequest, token: str, link_days: int) -> Email:
    summary = json.loads(request.summary_json or "{}")
    ref = f"{request.requisition_no} line {request.line_no}"
    link = f"{get_settings().app_url.rstrip('/')}/a/{token}"
    body = "\n".join(
        [
            f"Hi {request.approver_name},",
            "",
            f"Purchase requisition {ref} is waiting for your authorization.",
            "",
            *summary_lines(summary),
            "",
            "Review it and approve or reject here:",
            "",
            link,
            "",
            f"The link is for you only and works for {link_days} days. You can also authorize in IFS as usual.",
        ]
    )
    return Email(
        to=request.approver_email,
        subject=f"Approval needed: purchase requisition {ref}",
        text=body,
    )


# --- Decisions ---


def find_request_by_link(db: Session, token: str) -> tuple[ApprovalRequest, SecureLink] | None:
    link = links.find(db, token, LINK_PURPOSE)
    if link is None:
        return None
    request = db.scalar(select(ApprovalRequest).where(ApprovalRequest.link_id == link.id))
    if request is None:
        return None
    return request, link


def close_others(db: Session, request: ApprovalRequest) -> None:
    """Someone acted on the step: the other people's links for it stop working."""
    others = db.scalars(
        select(ApprovalRequest).where(
            ApprovalRequest.organization_id == request.organization_id,
            ApprovalRequest.kind == request.kind,
            ApprovalRequest.requisition_no == request.requisition_no,
            ApprovalRequest.line_no == request.line_no,
            ApprovalRequest.release_no == request.release_no,
            ApprovalRequest.sequence_no == request.sequence_no,
            ApprovalRequest.id != request.id,
            ApprovalRequest.status == SENT,
        )
    ).all()
    for other in others:
        other.status = CLOSED
        if other.link is not None:
            links.revoke(other.link)


def decide(
    db: Session,
    setup: ApprovalSetup,
    request: ApprovalRequest,
    link: SecureLink,
    decision: str,
    reason_id: str | None,
    note: str | None,
) -> str:
    """Sends the decision to IFS. Returns IFS's answer (APPROVED, REJECTED, SIGNED, NOT_YET).

    Raises IfsError when IFS refuses (for example, over the person's limit);
    the link then stays usable so they can try again or reject.
    """
    connection = setup.connection
    if decision == "approve":
        result = ifs_api.approve(connection, request)
    else:
        result = ifs_api.reject(connection, request, reason_id or "", note)

    if (decision, result) in (("approve", "APPROVED"), ("reject", "REJECTED")):
        request.status = APPROVED if decision == "approve" else REJECTED
        request.decided_at = _now()
        request.reject_reason_id = reason_id if decision == "reject" else None
        request.note = (note or None) and note[:2000]
        links.mark_used(link)
        close_others(db, request)
        usage.record(
            db, request.organization_id, APPROVALS, "approvals.decided", billable=True, ref=f"approval:{request.id}"
        )
    else:
        # Someone else signed it, it isn't this step's turn, or the line was rejected.
        request.status = CLOSED
        links.mark_used(link)
    request.error = None
    return result


def record_failure(db: Session, request: ApprovalRequest, message: str) -> None:
    request.error = message[:1000]
    usage.record(
        db, request.organization_id, APPROVALS, "approvals.failed", billable=False, ref=f"approval:{request.id}"
    )


def expire_stale_links(db: Session, org_id: int) -> None:
    """Marks requests whose link expired without a decision as closed (housekeeping for the log)."""
    db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.organization_id == org_id,
            ApprovalRequest.status == SENT,
            ApprovalRequest.link_id.in_(
                select(SecureLink.id).where(SecureLink.expires_at <= _now(), SecureLink.used_at.is_(None))
            ),
        )
        .values(status=CLOSED)
        .execution_options(synchronize_session=False)
    )
