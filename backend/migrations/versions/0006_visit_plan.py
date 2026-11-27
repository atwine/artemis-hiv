"""visit_plan: one row per AI management plan "Compare plans" made for a saved visit (owner,
2026-11-27). Rows are only ever added; the latest one for a visit is shown.

Revision ID: 0006
Revises: 0005
Created: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('visit_plan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('visit_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('made_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
    sa.Column('outcome', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('plan_text', sa.Text(), nullable=True),
    sa.Column('issues', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('error_type', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
    sa.ForeignKeyConstraint(['visit_id'], ['visit_check.visit_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('visit_plan', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visit_plan_visit_id'), ['visit_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('visit_plan', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visit_plan_visit_id'))

    op.drop_table('visit_plan')
