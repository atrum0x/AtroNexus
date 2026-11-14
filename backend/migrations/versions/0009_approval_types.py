"""approval types

Each organization picks the approval types it uses (approval_flow_settings),
and an approval request stores its record's keys as one generic object_key
instead of requisition-only columns. Organizations that already had approvals
set up keep purchase requisition lines switched on.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14 18:00:00

"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, Sequence[str], None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('approval_flow_settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organization_id', sa.Integer(), nullable=False),
    sa.Column('flow', sa.String(length=30), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'flow', name='uq_approval_flow_settings_org_flow')
    )
    with op.batch_alter_table('approval_flow_settings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_approval_flow_settings_organization_id'), ['organization_id'], unique=False)

    # Purchase requisition lines were the only type: keep them on where approvals were set up.
    conn = op.get_bind()
    now = datetime.now(timezone.utc)
    settings = sa.table('approval_flow_settings',
        sa.column('organization_id', sa.Integer), sa.column('flow', sa.String),
        sa.column('enabled', sa.Boolean), sa.column('updated_at', sa.DateTime(timezone=True)))
    org_ids = conn.execute(sa.text('SELECT organization_id FROM approval_setups')).scalars().all()
    if org_ids:
        op.bulk_insert(settings, [
            {'organization_id': org_id, 'flow': 'PR_LINE', 'enabled': True, 'updated_at': now} for org_id in org_ids
        ])

    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('object_key', sa.String(length=200), nullable=True))
    op.execute("UPDATE approval_requests SET object_key = requisition_no || '^' || line_no || '^' || release_no")
    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.drop_constraint('uq_approval_requests_step_person', type_='unique')
        batch_op.alter_column('object_key', existing_type=sa.String(length=200), nullable=False)
        batch_op.alter_column('kind', existing_type=sa.String(length=20), type_=sa.String(length=30),
                              existing_nullable=False)
        batch_op.drop_column('requisition_no')
        batch_op.drop_column('line_no')
        batch_op.drop_column('release_no')
        batch_op.create_unique_constraint('uq_approval_requests_step_person',
                                          ['organization_id', 'kind', 'object_key', 'sequence_no', 'fnd_user'])


def downgrade() -> None:
    # Only purchase requisition lines existed before; other types' requests are dropped.
    op.execute("DELETE FROM approval_requests WHERE kind <> 'PR_LINE'")
    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('requisition_no', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('line_no', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('release_no', sa.String(length=10), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text('SELECT id, object_key FROM approval_requests')).all()
    for row_id, key in rows:
        req, line, rel = (key.split('^') + ['', '', ''])[:3]
        conn.execute(sa.text('UPDATE approval_requests SET requisition_no = :r, line_no = :l, release_no = :e WHERE id = :i'),
                     {'r': req, 'l': line, 'e': rel, 'i': row_id})
    with op.batch_alter_table('approval_requests', schema=None) as batch_op:
        batch_op.drop_constraint('uq_approval_requests_step_person', type_='unique')
        batch_op.alter_column('requisition_no', existing_type=sa.String(length=20), nullable=False)
        batch_op.alter_column('line_no', existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column('release_no', existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column('kind', existing_type=sa.String(length=30), type_=sa.String(length=20),
                              existing_nullable=False)
        batch_op.drop_column('object_key')
        batch_op.create_unique_constraint('uq_approval_requests_step_person',
            ['organization_id', 'kind', 'requisition_no', 'line_no', 'release_no', 'sequence_no', 'fnd_user'])

    with op.batch_alter_table('approval_flow_settings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_approval_flow_settings_organization_id'))
    op.drop_table('approval_flow_settings')
