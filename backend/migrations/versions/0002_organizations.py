"""organizations

Adds the organizations table and an organization_id to users, IFS connections
and capture targets (captures belong to an organization through their target).

Everything that existed before belongs to the platform owner, so it moves into
one "AtroNexus" organization, and the existing users become its owners and
platform admins. On an empty database nothing is created here; the app's
admin seed creates the organization on startup.

Revision ID: 0002
Revises: 0001
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("users", "ifs_connections", "capture_targets")
EXISTING_ORG_NAME = "AtroNexus"


def _fk(table: str) -> str:
    return f"fk_{table}_organization_id_organizations"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 1. Add the new columns as nullable so existing rows are allowed.
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("role", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("is_platform_admin", sa.Boolean(), nullable=True))

    # 2. Move existing rows into one organization.
    bind = op.get_bind()
    has_rows = any(
        bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None
        for table in TABLES
    )
    if has_rows:
        orgs = sa.table(
            "organizations",
            sa.column("name", sa.String),
            sa.column("status", sa.String),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        bind.execute(
            orgs.insert().values(
                name=EXISTING_ORG_NAME, status="active", created_at=datetime.now(timezone.utc)
            )
        )
        org_id = bind.execute(sa.text("SELECT MAX(id) FROM organizations")).scalar_one()
        for table in TABLES:
            bind.execute(sa.text(f"UPDATE {table} SET organization_id = :org"), {"org": org_id})
        bind.execute(
            sa.text("UPDATE users SET role = 'owner', is_platform_admin = :yes"), {"yes": True}
        )

    # 3. Now every row has a value: make the columns required and link them.
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("organization_id", existing_type=sa.Integer(), nullable=False)
            batch.create_index(f"ix_{table}_organization_id", ["organization_id"], unique=False)
            batch.create_foreign_key(_fk(table), "organizations", ["organization_id"], ["id"])
    with op.batch_alter_table("users") as batch:
        batch.alter_column("role", existing_type=sa.String(length=20), nullable=False)
        batch.alter_column("is_platform_admin", existing_type=sa.Boolean(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_platform_admin")
        batch.drop_column("role")
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(_fk(table), type_="foreignkey")
            batch.drop_index(f"ix_{table}_organization_id")
            batch.drop_column("organization_id")
    op.drop_table("organizations")
