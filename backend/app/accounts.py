"""Creating organizations and users outside the API (startup seed and the CLI)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, User
from app.security import hash_password

# The organization the platform owner's own users belong to.
PLATFORM_ORG_NAME = "AtroNexus"


def get_or_create_org(db: Session, name: str) -> Organization:
    org = db.scalar(select(Organization).where(Organization.name == name).order_by(Organization.id))
    if org is None:
        org = Organization(name=name)
        db.add(org)
        db.flush()
    return org


def seed_platform_admin(db: Session, username: str, password: str) -> None:
    """Creates the platform admin on first start. Does nothing if the user exists."""
    if db.scalar(select(User).where(User.username == username)) is not None:
        return
    org = get_or_create_org(db, PLATFORM_ORG_NAME)
    db.add(
        User(
            organization=org,
            username=username,
            password_hash=hash_password(password),
            role="owner",
            is_platform_admin=True,
        )
    )
    db.commit()
