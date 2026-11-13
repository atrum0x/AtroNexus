"""Create a user or reset their password.

    uv run python -m app.cli create-user <username> [--org "Company name"] [--platform-admin]

A new user joins the organization with that name, which is created if it
doesn't exist (default: the platform's own organization). For an existing
user only the password changes.
"""

import argparse
import getpass
from datetime import datetime, timezone

from sqlalchemy import select

from app import migrate
from app.accounts import PLATFORM_ORG_NAME, get_or_create_org
from app.db import SessionLocal
from app.models import User
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="Create a user or reset their password")
    create.add_argument("username")
    create.add_argument("--org", default=PLATFORM_ORG_NAME, help="Organization name for a new user")
    create.add_argument("--platform-admin", action="store_true", help="Make a new user a platform admin")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if not password:
        raise SystemExit("Password can't be empty")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords don't match")

    migrate.upgrade()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is None:
            org = get_or_create_org(db, args.org)
            db.add(
                User(
                    organization=org,
                    username=args.username,
                    password_hash=hash_password(password),
                    role="owner",
                    is_platform_admin=args.platform_admin,
                    email_verified_at=datetime.now(timezone.utc),
                )
            )
            print(f"Created user {args.username} in {org.name}")
        else:
            user.password_hash = hash_password(password)
            print(f"Reset password for {args.username}")
        db.commit()


if __name__ == "__main__":
    main()
