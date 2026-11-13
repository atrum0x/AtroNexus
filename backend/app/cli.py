"""Create a user or reset their password: uv run python -m app.cli create-user <username>"""

import argparse
import getpass

from sqlalchemy import select

from app.db import Base, SessionLocal, engine
from app.models import User
from app.security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-user", help="Create a user or reset their password")
    create.add_argument("username")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if not password:
        raise SystemExit("Password can't be empty")
    if password != getpass.getpass("Repeat password: "):
        raise SystemExit("Passwords don't match")

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if user is None:
            db.add(User(username=args.username, password_hash=hash_password(password)))
            print(f"Created user {args.username}")
        else:
            user.password_hash = hash_password(password)
            print(f"Reset password for {args.username}")
        db.commit()


if __name__ == "__main__":
    main()
