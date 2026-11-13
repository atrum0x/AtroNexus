"""tools

Adds organization_tools (which tools each organization has switched on) and
tool_events (the on/off history billing will be based on).

Organizations that existed before tools could be switched were already using
the capture page, so it starts switched on for them. Organizations created
from now on start with no tools.

Revision ID: 0005
Revises: 0004
"""

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_tools",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_organization_tools_organization_id_organizations"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "tool", name="uq_organization_tools_org_tool"),
    )
    with op.batch_alter_table("organization_tools") as batch:
        batch.create_index("ix_organization_tools_organization_id", ["organization_id"], unique=False)

    op.create_table(
        "tool_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_tool_events_organization_id_organizations"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_tool_events_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("tool_events") as batch:
        batch.create_index("ix_tool_events_organization_id", ["organization_id"], unique=False)

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    org_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM organizations"))]
    for org_id in org_ids:
        bind.execute(
            sa.text(
                "INSERT INTO organization_tools (organization_id, tool, enabled, enabled_at, updated_at) "
                "VALUES (:org, 'capture', :yes, :now, :now)"
            ),
            {"org": org_id, "yes": True, "now": now},
        )
        bind.execute(
            sa.text(
                "INSERT INTO tool_events (organization_id, tool, enabled, user_id, created_at) "
                "VALUES (:org, 'capture', :yes, NULL, :now)"
            ),
            {"org": org_id, "yes": True, "now": now},
        )


def downgrade() -> None:
    op.drop_table("tool_events")
    op.drop_table("organization_tools")
