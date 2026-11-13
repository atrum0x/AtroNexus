from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import func, select

from app.capture import service
from app.capture.models import Capture, CaptureTarget
from app.capture.schemas import (
    REQUEST_ID_PATTERN,
    CaptureDefaults,
    CaptureLinkInfo,
    CaptureOut,
    CaptureResult,
    CaptureSubmit,
    CaptureTargetIn,
    CaptureTargetOut,
)
from app.capture.template import DEFAULT_BODY_TEMPLATE, DEFAULT_ENDPOINT_PATH, PLACEHOLDERS
from app.deps import DbSession, get_current_user
from app.ifs.client import IfsClient, IfsError
from app.ifs.models import IfsConnection
from app.ifs.schemas import CheckResult
from app.internal import client_ip

# --- Admin: capture page setups and the capture log ---

router = APIRouter(
    prefix="/api/capture",
    tags=["capture"],
    dependencies=[Depends(get_current_user)],
)


def _target_out(t: CaptureTarget) -> CaptureTargetOut:
    return CaptureTargetOut(
        id=t.id,
        public_id=t.public_id,
        name=t.name,
        connection_id=t.connection_id,
        connection_name=t.connection.name,
        endpoint_path=t.endpoint_path,
        http_method=t.http_method,  # type: ignore[arg-type]
        body_template=t.body_template,
        enabled=t.enabled,
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _capture_out(c: Capture) -> CaptureOut:
    return CaptureOut(
        id=c.id,
        target_id=c.target_id,
        target_name=c.target.name,
        request_id=c.request_id,
        status=c.status,
        latitude=c.latitude,
        longitude=c.longitude,
        accuracy=c.accuracy,
        location_error=c.location_error,
        ip=c.ip,
        user_agent=c.user_agent,
        platform=c.platform,
        screen=c.screen,
        captured_at=c.captured_at,
        writeback_status=c.writeback_status,
        writeback_error=c.writeback_error,
        sent_at=c.sent_at,
    )


def _get_target(db: DbSession, target_id: int) -> CaptureTarget:
    target = db.get(CaptureTarget, target_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capture page not found")
    return target


def _apply(db: DbSession, target: CaptureTarget, body: CaptureTargetIn) -> None:
    connection = db.get(IfsConnection, body.connection_id)
    if connection is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick an existing IFS connection.")
    target.name = body.name.strip()
    target.connection = connection
    target.endpoint_path = body.endpoint_path.strip()
    target.http_method = body.http_method
    target.body_template = body.body_template
    target.enabled = body.enabled


@router.get("/defaults", response_model=CaptureDefaults)
def get_capture_defaults() -> CaptureDefaults:
    return CaptureDefaults(
        endpoint_path=DEFAULT_ENDPOINT_PATH,
        http_method="PATCH",
        body_template=DEFAULT_BODY_TEMPLATE,
        placeholders=PLACEHOLDERS,
    )


@router.get("/targets", response_model=list[CaptureTargetOut])
def list_capture_targets(db: DbSession) -> list[CaptureTargetOut]:
    rows = db.scalars(select(CaptureTarget).order_by(CaptureTarget.name)).all()
    return [_target_out(t) for t in rows]


@router.post("/targets", response_model=CaptureTargetOut, status_code=status.HTTP_201_CREATED)
def create_capture_target(body: CaptureTargetIn, db: DbSession) -> CaptureTargetOut:
    target = CaptureTarget()
    _apply(db, target, body)
    db.add(target)
    db.commit()
    return _target_out(target)


@router.get("/targets/{target_id}", response_model=CaptureTargetOut)
def get_capture_target(target_id: int, db: DbSession) -> CaptureTargetOut:
    return _target_out(_get_target(db, target_id))


@router.put("/targets/{target_id}", response_model=CaptureTargetOut)
def update_capture_target(target_id: int, body: CaptureTargetIn, db: DbSession) -> CaptureTargetOut:
    target = _get_target(db, target_id)
    _apply(db, target, body)
    db.commit()
    return _target_out(target)


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_capture_target(target_id: int, db: DbSession) -> None:
    target = _get_target(db, target_id)
    used = db.scalar(select(func.count()).select_from(Capture).where(Capture.target_id == target.id))
    if used:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This capture page has captures in the log. Turn it off instead of deleting it.",
        )
    db.delete(target)
    db.commit()


@router.post("/targets/{target_id}/test", response_model=CheckResult)
def test_capture_target(target_id: int, db: DbSession) -> CheckResult:
    """Signs in and reads the projection's service root, without writing anything."""
    target = _get_target(db, target_id)
    path = target.endpoint_path
    marker = path.find(".svc")
    service_root = path[: marker + len(".svc")] + "/" if marker != -1 else None
    client = IfsClient(target.connection)
    try:
        client.authenticate()
        if service_root is None:
            return CheckResult(
                ok=True,
                message="Signed in to IFS. The endpoint isn't a projection (.svc) path, so it wasn't checked.",
            )
        client.request("GET", service_root)
        return CheckResult(ok=True, message=f"Signed in to IFS and reached {service_root}")
    except IfsError as exc:
        return CheckResult(ok=False, message=exc.message)
    except ValueError as exc:
        return CheckResult(ok=False, message=str(exc))


@router.get("/captures", response_model=list[CaptureOut])
def list_captures(
    db: DbSession,
    target_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[CaptureOut]:
    query = select(Capture).order_by(Capture.captured_at.desc()).limit(limit)
    if target_id is not None:
        query = query.where(Capture.target_id == target_id)
    return [_capture_out(c) for c in db.scalars(query).all()]


# --- Public: called by the capture page, no login ---

public_router = APIRouter(prefix="/api/public/capture", tags=["capture-public"])

PublicId = Annotated[str, Path(max_length=32)]
RequestId = Annotated[str, Path(pattern=REQUEST_ID_PATTERN)]


def _public_target(db: DbSession, public_id: str) -> CaptureTarget:
    target = db.scalar(select(CaptureTarget).where(CaptureTarget.public_id == public_id))
    if target is None or not target.enabled:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This capture link isn't valid.")
    return target


@public_router.get("/{public_id}/{request_id}", response_model=CaptureLinkInfo)
def get_capture_link(public_id: PublicId, request_id: RequestId, db: DbSession) -> CaptureLinkInfo:
    target = _public_target(db, public_id)
    sent = db.scalar(
        select(func.count())
        .select_from(Capture)
        .where(
            Capture.target_id == target.id,
            Capture.request_id == request_id,
            Capture.writeback_status == "sent",
        )
    )
    return CaptureLinkInfo(target_name=target.name, request_id=request_id, already_sent=bool(sent))


@public_router.post("/{public_id}/{request_id}", response_model=CaptureResult)
def submit_capture(
    public_id: PublicId,
    request_id: RequestId,
    body: CaptureSubmit,
    request: Request,
    db: DbSession,
) -> CaptureResult:
    target = _public_target(db, public_id)
    # The page posts through the Next.js server, which passes the browser's
    # address in X-Client-IP. See app/internal.py for when it's trusted.
    try:
        capture = service.submit(db, target, request_id, body, client_ip(request))
    except service.AlreadySent:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This request was already captured. You can close this tab."
        ) from None

    if capture.writeback_status == "sent":
        return CaptureResult(ok=True, message="Saved to IFS.")
    return CaptureResult(ok=False, message=capture.writeback_error or "IFS didn't accept the capture.")
