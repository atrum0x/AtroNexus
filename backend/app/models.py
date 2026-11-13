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
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="owner")
    # Runs the platform (sees every organization). Not tied to the user's own organization.
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=_now)

    organization: Mapped[Organization] = relationship(lazy="joined")
