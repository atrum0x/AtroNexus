"""Calls to the IFS package's projection CAtxApprovalHandling."""

import json
from dataclasses import dataclass
from typing import Any

from app.approvals.models import ApprovalRequest
from app.crypto import decrypt
from app.ifs.client import IfsClient
from app.ifs.models import IfsConnection

SERVICE = "/main/ifsapplications/projection/v1/CAtxApprovalHandling.svc"


@dataclass
class LineStatus:
    status: str  # PENDING, SIGNED, NOT_YET, REJECTED
    signed_by: str | None
    summary: dict[str, Any]


def _params(request: ApprovalRequest) -> dict[str, Any]:
    return {
        "RequisitionNo": request.requisition_no,
        "LineNo": request.line_no,
        "ReleaseNo": request.release_no,
        "SequenceNo": request.sequence_no,
        "FndUser": request.fnd_user,
        "IssuedAt": request.issued_at,
        "Token": decrypt(request.ifs_token_enc),
    }


def _call(connection: IfsConnection, action: str, body: dict[str, Any]) -> Any:
    res = IfsClient(connection).request("POST", f"{SERVICE}/{action}", json=body)
    return res.body.get("value") if isinstance(res.body, dict) else res.body


def check_package(connection: IfsConnection) -> None:
    """Raises IfsError unless the package is deployed and the service user may use it."""
    IfsClient(connection).request("GET", f"{SERVICE}/")


def line_status(connection: IfsConnection, request: ApprovalRequest) -> LineStatus:
    data = json.loads(_call(connection, "GetPrLineStatus", _params(request)) or "{}")
    return LineStatus(
        status=str(data.get("status") or "PENDING"),
        signed_by=data.get("signedBy"),
        summary=data.get("summary") or {},
    )


def reject_reasons(connection: IfsConnection, request: ApprovalRequest) -> list[dict[str, str]]:
    data = json.loads(_call(connection, "GetRejectReasons", _params(request)) or "[]")
    return [{"id": str(r.get("id")), "description": str(r.get("description") or r.get("id"))} for r in data]


def approve(connection: IfsConnection, request: ApprovalRequest) -> str:
    """APPROVED, or SIGNED / NOT_YET / REJECTED when the step can't be approved now."""
    return str(_call(connection, "ApprovePrLine", _params(request)))


def reject(connection: IfsConnection, request: ApprovalRequest, reason_id: str, note: str | None) -> str:
    """REJECTED, or SIGNED / NOT_YET when the step can't be rejected now."""
    return str(
        _call(connection, "RejectPrLine", {**_params(request), "RejectReasonId": reason_id, "RejectNote": note or ""})
    )
