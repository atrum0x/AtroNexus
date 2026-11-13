"""organization status reason

Adds when and why an organization was last suspended or reactivated by the
platform admin.

Revision ID: 0007
Revises: 0006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.add_column(sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("status_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch:
        batch.drop_column("status_reason")
        batch.drop_column("status_changed_at")
