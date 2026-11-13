"""Saves a capture and writes it back to IFS."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.capture.models import Capture, CaptureTarget
from app.capture.schemas import CaptureSubmit
from app.capture.template import render_body, render_path
from app.ifs.client import IfsClient, IfsError
from app.tools.catalog import CAPTURE
from app.usage import service as usage

STATUS_LABELS = {"captured": "Captured", "denied": "Denied", "unavailable": "Unavailable"}


class AlreadySent(Exception):
    pass


def submit(
    db: Session, target: CaptureTarget, request_id: str, data: CaptureSubmit, ip: str | None
) -> Capture:
    """Records the capture, then sends it to IFS. Returns the capture with its write-back result.

    A request ID can be sent to IFS once. If an earlier attempt failed, a new
    submission replaces it and tries again.
    """
    capture = db.scalar(
        select(Capture).where(Capture.target_id == target.id, Capture.request_id == request_id)
    )
    if capture is not None and capture.writeback_status == "sent":
        raise AlreadySent()
    if capture is None:
        capture = Capture(target_id=target.id, request_id=request_id)
        db.add(capture)

    capture.status = data.status
    capture.latitude = data.latitude
    capture.longitude = data.longitude
    capture.accuracy = data.accuracy
    capture.location_error = data.location_error
    capture.ip = ip
    capture.user_agent = data.user_agent
    capture.platform = data.platform
    capture.language = data.language
    capture.time_zone = data.time_zone
    capture.screen = data.screen
    capture.captured_at = datetime.now(timezone.utc)
    capture.writeback_status = "pending"
    capture.writeback_error = None
    db.commit()

    try:
        write_back(target, capture)
    except (IfsError, ValueError) as exc:
        capture.writeback_status = "failed"
        capture.writeback_error = getattr(exc, "message", str(exc))[:1000]
        usage.record(db, target.organization_id, CAPTURE, usage.CAPTURE_FAILED, billable=False,
                     ref=f"capture:{capture.id}")
    else:
        capture.writeback_status = "sent"
        capture.sent_at = datetime.now(timezone.utc)
        usage.record(db, target.organization_id, CAPTURE, usage.CAPTURE_SENT, billable=True,
                     ref=f"capture:{capture.id}")
    db.commit()
    return capture


def write_back(target: CaptureTarget, capture: Capture) -> None:
    client = IfsClient(target.connection)
    path = render_path(target.endpoint_path, capture.request_id)
    body = render_body(target.body_template, template_values(capture))

    headers: dict[str, str] = {}
    if target.http_method == "PATCH":
        # IFS projections only accept a PATCH with the record's current ETag.
        # Reading the record first also proves the request ID exists in IFS.
        try:
            current = client.request("GET", path)
        except IfsError as exc:
            if exc.status_code == 404:
                raise IfsError("IFS has no capture request with this ID.", 404) from exc
            raise
        etag = current.headers.get("ETag")
        if not etag and isinstance(current.body, dict):
            etag = current.body.get("@odata.etag")
        headers["If-Match"] = etag or "*"

    client.request(target.http_method, path, json=body, headers=headers)


def template_values(capture: Capture) -> dict[str, Any]:
    device = ", ".join(p for p in (capture.platform, capture.screen, capture.language) if p)
    return {
        "request_id": capture.request_id,
        "status": STATUS_LABELS.get(capture.status, capture.status),
        "latitude": capture.latitude,
        "longitude": capture.longitude,
        "accuracy": round(capture.accuracy, 1) if capture.accuracy is not None else None,
        "location_error": capture.location_error,
        "ip": capture.ip,
        "user_agent": capture.user_agent,
        "platform": capture.platform,
        "language": capture.language,
        "time_zone": capture.time_zone,
        "screen": capture.screen,
        "device": device or None,
        "captured_at": capture.captured_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
    }
