"""Organizations, users and one-time email links."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.email.sender import Email
from app.models import RESET_PASSWORD, VERIFY_EMAIL, AuthToken, Organization, User
from app.security import hash_link_token, hash_password, new_link_token

# The organization the platform owner's own users belong to.
PLATFORM_ORG_NAME = "AtroNexus"

LINK_LIFETIME = {
    VERIFY_EMAIL: timedelta(days=2),
    RESET_PASSWORD: timedelta(hours=1),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def find_user_for_login(db: Session, identifier: str) -> User | None:
    """By email, or by username for users from before email sign-in."""
    value = identifier.strip()
    return db.scalar(
        select(User).where(or_(User.email == normalize_email(value), User.username == value))
    )


def email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(func.count()).select_from(User).where(User.email == normalize_email(email))) > 0


def get_or_create_org(db: Session, name: str) -> Organization:
    org = db.scalar(select(Organization).where(Organization.name == name).order_by(Organization.id))
    if org is None:
        org = Organization(name=name)
        db.add(org)
        db.flush()
    return org


def sign_up(db: Session, organization_name: str, name: str, email: str, password: str) -> User:
    """A new organization with its first user as owner. The email is unverified."""
    org = Organization(name=organization_name.strip())
    user = User(
        organization=org,
        email=normalize_email(email),
        name=name.strip(),
        password_hash=hash_password(password),
        role="owner",
    )
    db.add_all([org, user])
    db.flush()
    return user


def seed_platform_admin(
    db: Session, username: str, password: str, email: str | None = None
) -> None:
    """Creates the platform admin on first start, and gives them ADMIN_EMAIL if they have none."""
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        org = get_or_create_org(db, PLATFORM_ORG_NAME)
        # The platform's own organization gets every tool that exists.
        from app.tools.catalog import TOOLS
        from app.tools.service import set_enabled

        for tool in TOOLS:
            if tool.available:
                set_enabled(db, org.id, tool.code, True, None)
        user = User(
            organization=org,
            username=username,
            password_hash=hash_password(password),
            role="owner",
            is_platform_admin=True,
            email_verified_at=_now(),
        )
        db.add(user)
    if email and user.email is None and not email_taken(db, email):
        user.email = normalize_email(email)
        user.email_verified_at = user.email_verified_at or _now()
    db.commit()


# --- One-time email links ---


def create_link(db: Session, user: User, purpose: str) -> str:
    """Returns the token for the link. Earlier unused links for the same purpose stop working."""
    _expire_links(db, user, purpose)
    token, token_hash = new_link_token()
    db.add(
        AuthToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=token_hash,
            expires_at=_now() + LINK_LIFETIME[purpose],
        )
    )
    return token


def use_link(db: Session, token: str, purpose: str) -> User | None:
    """Marks the link used and returns its user, or None if it's unknown, used or expired."""
    row = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_link_token(token)))
    if row is None or row.purpose != purpose or row.used_at is not None or row.expires_at <= _now():
        return None
    row.used_at = _now()
    return row.user


def _expire_links(db: Session, user: User, purpose: str) -> None:
    db.execute(
        update(AuthToken)
        .where(AuthToken.user_id == user.id, AuthToken.purpose == purpose, AuthToken.used_at.is_(None))
        .values(used_at=_now())
    )


def set_password(db: Session, user: User, password: str) -> None:
    """Changes the password and ends every existing session of this user."""
    user.password_hash = hash_password(password)
    user.password_changed_at = _now()
    _expire_links(db, user, RESET_PASSWORD)


# --- Emails ---


def _link(path: str, token: str) -> str:
    return f"{get_settings().app_url.rstrip('/')}{path}?token={token}"


def verify_email_message(user: User, token: str) -> Email:
    return Email(
        to=user.email or "",
        subject="Confirm your email for AtroNexus",
        text=(
            f"Hi {user.name or 'there'},\n\n"
            f"Confirm your email address to finish setting up {user.organization.name} on AtroNexus:\n\n"
            f"{_link('/verify-email', token)}\n\n"
            "The link works for 2 days. If you didn't sign up, you can ignore this email.\n"
        ),
    )


def reset_password_message(user: User, token: str) -> Email:
    return Email(
        to=user.email or "",
        subject="Reset your AtroNexus password",
        text=(
            f"Hi {user.name or 'there'},\n\n"
            "Someone (hopefully you) asked to reset your AtroNexus password. Choose a new one here:\n\n"
            f"{_link('/reset-password', token)}\n\n"
            "The link works for 1 hour and only once. If you didn't ask for this, ignore this email; "
            "your password stays the same.\n"
        ),
    )
