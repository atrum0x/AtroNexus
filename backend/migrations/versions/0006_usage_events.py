"""usage events

Adds usage_events: one row per counted use of a tool, the base for usage
numbers and later per-use billing.

Captures made before usage was counted are backfilled, one event each, so the
dashboard has history: sent captures count on the day they were sent, failed
ones as failures on the day they were captured. (A retried capture overwrites
its earlier failure, so older failures of later-successful captures are lost.)

Revision ID: 0006
Revises: 0005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("billable", sa.Boolean(), nullable=False),
        sa.Column("ref", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], name="fk_usage_events_organization_id_organizations"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("usage_events") as batch:
        batch.create_index("ix_usage_events_org_created", ["organization_id", "created_at"], unique=False)

    # Done in SQL so the timestamps stay database values (SQLite hands raw
    # selects back as text).
    op.execute(
        "INSERT INTO usage_events (organization_id, tool, kind, quantity, billable, ref, created_at) "
        "SELECT t.organization_id, 'capture', "
        "CASE WHEN c.writeback_status = 'sent' THEN 'capture.sent' ELSE 'capture.failed' END, "
        "1, c.writeback_status = 'sent', 'capture:' || c.id, "
        "CASE WHEN c.writeback_status = 'sent' THEN COALESCE(c.sent_at, c.captured_at) ELSE c.captured_at END "
        "FROM captures c JOIN capture_targets t ON t.id = c.target_id "
        "WHERE c.writeback_status IN ('sent', 'failed')"
    )


def downgrade() -> None:
    op.drop_table("usage_events")
