"""Team rules: who may change whom, and invitations."""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.accounts import normalize_email
from app.config import get_settings
from app.email.sender import Email
from app.models import ORG_ACTIVE, AuthToken, Invitation, User
from app.security import hash_link_token, new_link_token

INVITE_LIFETIME = timedelta(days=7)
ROLE_LABELS = {"owner": "Owner", "admin": "Admin", "member": "Member"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _forbidden(message: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, message)


def display_name(user: User | None) -> str | None:
    if user is None:
        return None
    return user.name or user.email or user.username


# --- Who may change whom ---


def check_can_manage_member(actor: User, member: User, new_role: str | None = None) -> None:
    """Raises 403 unless actor may change member's role (to new_role) or remove them.

    - Only owners and admins manage the team.
    - Nobody changes or removes themselves, so an organization can't lock
      itself out by accident.
    - Owners, and making someone an owner, are for owners only.
    """
    if actor.role not in ("owner", "admin"):
        raise _forbidden("Only owners and admins can manage the team.")
    if member.id == actor.id:
        raise _forbidden("You can't change or remove your own account. Ask another owner.")
    if actor.role != "owner" and (member.role == "owner" or new_role == "owner"):
        raise _forbidden("Only owners can change owners or make someone an owner.")


def ensure_an_owner_remains(db: Session, member: User, new_role: str | None) -> None:
    """Refuses to demote or remove the organization's last owner."""
    if member.role != "owner" or new_role == "owner":
        return
    owners = db.scalar(
        select(func.count())
        .select_from(User)
        .where(User.organization_id == member.organization_id, User.role == "owner", User.is_active)
    )
    if owners <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "An organization needs at least one owner.")


def remove_member(db: Session, member: User) -> None:
    # Done here rather than by the database, because SQLite doesn't enforce
    # ON DELETE unless foreign keys are switched on.
    db.execute(delete(AuthToken).where(AuthToken.user_id == member.id))
    db.execute(update(Invitation).where(Invitation.invited_by_id == member.id).values(invited_by_id=None))
    db.delete(member)


# --- Invitations ---


def create_invitation(db: Session, actor: User, email: str, role: str) -> tuple[Invitation, str]:
    """Returns the invitation and the token for its link."""
    if actor.role not in ("owner", "admin"):
        raise _forbidden("Only owners and admins can invite people.")
    if role == "owner" and actor.role != "owner":
        raise _forbidden("Only owners can invite an owner.")
    email = normalize_email(email)
    if db.scalar(select(func.count()).select_from(User).where(User.email == email)):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This email already has an AtroNexus account. For now, an account belongs to one organization.",
        )
    # A new invite replaces an older pending one to the same address.
    db.execute(
        update(Invitation)
        .where(
            Invitation.organization_id == actor.organization_id,
            Invitation.email == email,
            Invitation.accepted_at.is_(None),
            Invitation.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    token, token_hash = new_link_token()
    invitation = Invitation(
        organization_id=actor.organization_id,
        email=email,
        role=role,
        token_hash=token_hash,
        invited_by_id=actor.id,
        expires_at=_now() + INVITE_LIFETIME,
    )
    db.add(invitation)
    db.flush()
    return invitation, token


def pending_invitations(db: Session, org_id: int) -> list[Invitation]:
    return list(
        db.scalars(
            select(Invitation)
            .where(
                Invitation.organization_id == org_id,
                Invitation.accepted_at.is_(None),
                Invitation.revoked_at.is_(None),
                Invitation.expires_at > _now(),
            )
            .order_by(Invitation.created_at.desc())
        ).all()
    )


def find_open_invitation(db: Session, token: str) -> Invitation | None:
    """The invitation behind a link, if it can still be accepted."""
    inv = db.scalar(select(Invitation).where(Invitation.token_hash == hash_link_token(token)))
    if (
        inv is None
        or inv.accepted_at is not None
        or inv.revoked_at is not None
        or inv.expires_at <= _now()
        or inv.organization.status != ORG_ACTIVE
    ):
        return None
    return inv


def invitation_message(invitation: Invitation, token: str) -> Email:
    inviter = display_name(invitation.invited_by) or "Someone"
    link = f"{get_settings().app_url.rstrip('/')}/invite?token={token}"
    return Email(
        to=invitation.email,
        subject=f"{inviter} invited you to {invitation.organization.name} on AtroNexus",
        text=(
            f"{inviter} invited you to join {invitation.organization.name} on AtroNexus "
            f"as {ROLE_LABELS[invitation.role].lower()}.\n\n"
            f"Accept the invitation and choose a password here:\n\n{link}\n\n"
            "The link works for 7 days and only once. If you weren't expecting this, you can ignore it.\n"
        ),
    )
