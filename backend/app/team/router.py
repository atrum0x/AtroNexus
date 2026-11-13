from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
from sqlalchemy import select

from app.accounts import email_taken
from app.deps import CurrentUser, DbSession, ManagerOnly, OrgId, VerifiedEmail, get_current_user
from app.email.sender import send_email
from app.models import Invitation, User
from app.schemas import TokenResponse
from app.security import create_access_token, hash_password
from app.team import service
from app.team.schemas import (
    AcceptInvitation,
    InvitationIn,
    InvitationInfo,
    InvitationOut,
    MemberOut,
    RoleChange,
)

# --- Signed in: the organization's team ---

router = APIRouter(prefix="/api/team", tags=["team"], dependencies=[Depends(get_current_user)])


def _member_out(user: User, me: User) -> MemberOut:
    return MemberOut(
        id=user.id,
        name=user.name,
        email=user.email,
        username=user.username,
        role=user.role,  # type: ignore[arg-type]
        is_me=user.id == me.id,
        created_at=user.created_at,
    )


def _invitation_out(inv: Invitation) -> InvitationOut:
    return InvitationOut(
        id=inv.id,
        email=inv.email,
        role=inv.role,  # type: ignore[arg-type]
        invited_by=service.display_name(inv.invited_by),
        created_at=inv.created_at,
        expires_at=inv.expires_at,
    )


def _get_member(db: DbSession, org_id: int, member_id: int) -> User:
    member = db.get(User, member_id)
    if member is None or member.organization_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return member


@router.get("/members", response_model=list[MemberOut])
def list_members(db: DbSession, org_id: OrgId, me: CurrentUser) -> list[MemberOut]:
    rows = db.scalars(select(User).where(User.organization_id == org_id).order_by(User.created_at)).all()
    return [_member_out(u, me) for u in rows]


@router.put("/members/{member_id}/role", response_model=MemberOut)
def change_member_role(
    member_id: int, body: RoleChange, db: DbSession, org_id: OrgId, me: CurrentUser
) -> MemberOut:
    member = _get_member(db, org_id, member_id)
    service.check_can_manage_member(me, member, body.role)
    service.ensure_an_owner_remains(db, member, body.role)
    member.role = body.role
    db.commit()
    return _member_out(member, me)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: int, db: DbSession, org_id: OrgId, me: CurrentUser) -> None:
    member = _get_member(db, org_id, member_id)
    service.check_can_manage_member(me, member)
    service.ensure_an_owner_remains(db, member, None)
    service.remove_member(db, member)
    db.commit()


@router.get("/invitations", response_model=list[InvitationOut], dependencies=[ManagerOnly])
def list_invitations(db: DbSession, org_id: OrgId) -> list[InvitationOut]:
    return [_invitation_out(i) for i in service.pending_invitations(db, org_id)]


# VerifiedEmail: invites send email to any address, so only from confirmed accounts.
@router.post(
    "/invitations",
    response_model=InvitationOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[ManagerOnly, VerifiedEmail],
)
def create_invitation(
    body: InvitationIn, db: DbSession, me: CurrentUser, background: BackgroundTasks
) -> InvitationOut:
    invitation, token = service.create_invitation(db, me, body.email, body.role)
    db.commit()
    background.add_task(send_email, service.invitation_message(invitation, token))
    return _invitation_out(invitation)


@router.delete(
    "/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[ManagerOnly]
)
def revoke_invitation(invitation_id: int, db: DbSession, org_id: OrgId, me: CurrentUser) -> None:
    inv = db.get(Invitation, invitation_id)
    if inv is None or inv.organization_id != org_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if inv.role == "owner" and me.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only owners can cancel an owner invitation.")
    if inv.revoked_at is None and inv.accepted_at is None:
        inv.revoked_at = datetime.now(timezone.utc)
        db.commit()


# --- Public: the invite link, no login ---

public_router = APIRouter(prefix="/api/public/invitations", tags=["team-public"])

InviteToken = Path(min_length=1, max_length=200)
INVALID = "This invitation is invalid, was already used, or has expired. Ask for a new one."


def _open_invitation(db: DbSession, token: str) -> Invitation:
    inv = service.find_open_invitation(db, token)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, INVALID)
    return inv


@public_router.get("/{token}", response_model=InvitationInfo)
def get_invitation(db: DbSession, token: str = InviteToken) -> InvitationInfo:
    inv = _open_invitation(db, token)
    return InvitationInfo(
        organization_name=inv.organization.name,
        email=inv.email,
        role=inv.role,  # type: ignore[arg-type]
        invited_by=service.display_name(inv.invited_by),
    )


@public_router.post("/{token}/accept", response_model=TokenResponse)
def accept_invitation(body: AcceptInvitation, db: DbSession, token: str = InviteToken) -> TokenResponse:
    """Creates the account in the inviting organization and signs in."""
    inv = _open_invitation(db, token)
    if email_taken(db, inv.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This email already has an AtroNexus account. Sign in instead."
        )
    now = datetime.now(timezone.utc)
    user = User(
        organization_id=inv.organization_id,
        email=inv.email,
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        role=inv.role,
        # The link reached their inbox, which proves the address.
        email_verified_at=now,
    )
    db.add(user)
    inv.accepted_at = now
    db.commit()
    access, expires_in = create_access_token(user.id)
    return TokenResponse(access_token=access, expires_in=expires_in)
