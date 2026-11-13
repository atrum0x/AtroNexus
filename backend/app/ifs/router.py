from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select

from app.crypto import encrypt
from app.deps import DbSession, OrgId, VerifiedEmail, get_current_user
from app.ifs.client import IfsClient, IfsError, forget_token
from app.ifs.models import IfsConnection
from app.ifs.schemas import CheckResult, IfsConnectionIn, IfsConnectionOut

router = APIRouter(
    prefix="/api/ifs-connections",
    tags=["ifs-connections"],
    dependencies=[Depends(get_current_user)],
)


def _out(conn: IfsConnection) -> IfsConnectionOut:
    # Built field by field so the encrypted secret can never leak into a response.
    return IfsConnectionOut(
        id=conn.id,
        name=conn.name,
        base_url=conn.base_url,
        auth_type=conn.auth_type,  # type: ignore[arg-type]
        token_url=conn.token_url,
        client_id=conn.client_id,
        username=conn.username,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


def get_org_connection(db: DbSession, org_id: int, connection_id: int) -> IfsConnection | None:
    """The connection, or None when it doesn't exist or belongs to another organization."""
    conn = db.get(IfsConnection, connection_id)
    if conn is None or conn.organization_id != org_id:
        return None
    return conn


def _get(db: DbSession, org_id: int, connection_id: int) -> IfsConnection:
    conn = get_org_connection(db, org_id, connection_id)
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return conn


def _apply(conn: IfsConnection, body: IfsConnectionIn) -> None:
    conn.name = body.name.strip()
    conn.base_url = str(body.base_url).rstrip("/")
    conn.auth_type = body.auth_type
    if body.auth_type == "oauth2":
        conn.token_url = str(body.token_url)
        conn.client_id = body.client_id
        conn.username = None
    else:
        conn.username = body.username
        conn.token_url = None
        conn.client_id = None
    if body.secret:
        conn.secret_enc = encrypt(body.secret)


@router.get("", response_model=list[IfsConnectionOut])
def list_connections(db: DbSession, org_id: OrgId) -> list[IfsConnectionOut]:
    rows = db.scalars(
        select(IfsConnection)
        .where(IfsConnection.organization_id == org_id)
        .order_by(IfsConnection.name)
    ).all()
    return [_out(c) for c in rows]


@router.post("", response_model=IfsConnectionOut, status_code=status.HTTP_201_CREATED, dependencies=[VerifiedEmail])
def create_connection(body: IfsConnectionIn, db: DbSession, org_id: OrgId) -> IfsConnectionOut:
    if not body.secret:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Enter the client secret or password."
        )
    conn = IfsConnection(organization_id=org_id)
    _apply(conn, body)
    db.add(conn)
    db.commit()
    return _out(conn)


@router.get("/{connection_id}", response_model=IfsConnectionOut)
def get_connection(connection_id: int, db: DbSession, org_id: OrgId) -> IfsConnectionOut:
    return _out(_get(db, org_id, connection_id))


@router.put("/{connection_id}", response_model=IfsConnectionOut, dependencies=[VerifiedEmail])
def update_connection(
    connection_id: int, body: IfsConnectionIn, db: DbSession, org_id: OrgId
) -> IfsConnectionOut:
    conn = _get(db, org_id, connection_id)
    _apply(conn, body)
    db.commit()
    forget_token(conn.id)
    return _out(conn)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(connection_id: int, db: DbSession, org_id: OrgId) -> None:
    from app.capture.models import CaptureTarget

    conn = _get(db, org_id, connection_id)
    in_use = db.scalar(
        select(func.count()).select_from(CaptureTarget).where(CaptureTarget.connection_id == conn.id)
    )
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "A capture page uses this connection. Delete or change it first."
        )
    db.delete(conn)
    db.commit()
    forget_token(connection_id)


@router.post("/{connection_id}/test", response_model=CheckResult, dependencies=[VerifiedEmail])
def test_connection(connection_id: int, db: DbSession, org_id: OrgId) -> CheckResult:
    conn = _get(db, org_id, connection_id)
    client = IfsClient(conn)
    try:
        if conn.auth_type == "oauth2":
            client.authenticate()
            return CheckResult(ok=True, message="Signed in to IFS and got an access token.")
        # Basic auth has no token step, so make a real call to check it.
        client.request("GET", "/main/ifsapplications/projection/v1/")
        return CheckResult(ok=True, message="IFS accepted the username and password.")
    except IfsError as exc:
        if conn.auth_type == "basic" and exc.status_code and exc.status_code not in (401, 403):
            # Any answer other than 401/403 means the credentials got through.
            return CheckResult(
                ok=True, message=f"IFS accepted the username and password (answered {exc.status_code})."
            )
        return CheckResult(ok=False, message=exc.message)
    except ValueError as exc:
        return CheckResult(ok=False, message=str(exc))
