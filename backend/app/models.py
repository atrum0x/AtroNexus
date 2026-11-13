from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UtcDateTime


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Organization.status
ORG_ACTIVE = "active"
ORG_SUSPENDED = "suspended"

# User.role. Step 3 of the SaaS plan enforces them; for now every role can do everything.
ROLES = ("owner", "admin", "member")


class Organization(Base):
    """A customer company. Everything a customer sets up belongs to one."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # "active" or "suspended". A suspended organization can't sign in and its
    # public links stop working.
    status: Mapped[str] = mapped_column(String(20), default=ORG_ACTIVE)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    # Signs in with the email. Stored lowercase. Users from before sign-up
    # existed may have none and sign in with their username instead.
    email: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(100))
    # Only users created before email sign-in (and the CLI) have one.
    username: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # Sessions issued before this stop working (set by a password reset).
    password_changed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    role: Mapped[str] = mapped_column(String(20), default="owner")
    # Runs the platform (sees every organization). Not tied to the user's own organization.
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)

    organization: Mapped[Organization] = relationship(lazy="joined")


# AuthToken.purpose
VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"


class AuthToken(Base):
    """A one-time link sent by email (verify the address, reset the password).

    Only a SHA-256 hash of the token is stored, so a database leak doesn't
    leak working links.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(30))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)

    user: Mapped[User] = relationship(lazy="joined")
