"""email accounts

Users sign in with an email address. Adds email, name, email_verified_at and
password_changed_at to users, makes username optional (only older users have
one), and adds auth_tokens for one-time email links.

Existing users count as verified: they were created by the platform owner.

Revision ID: 0003
Revises: 0002
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("email", sa.String(length=254), nullable=True))
        batch.add_column(sa.Column("name", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("username", existing_type=sa.String(length=64), nullable=True)
        batch.create_index("ix_users_email", ["email"], unique=True)

    op.get_bind().execute(
        sa.text("UPDATE users SET email_verified_at = :now"), {"now": datetime.now(timezone.utc)}
    )

    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_auth_tokens_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("auth_tokens") as batch:
        batch.create_index("ix_auth_tokens_user_id", ["user_id"], unique=False)
        batch.create_index("ix_auth_tokens_token_hash", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("auth_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email")
        batch.alter_column("username", existing_type=sa.String(length=64), nullable=False)
        batch.drop_column("password_changed_at")
        batch.drop_column("email_verified_at")
        batch.drop_column("name")
        batch.drop_column("email")
