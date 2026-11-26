"""visit_finalize: one row per Finalize of a visit, never changed (owner, 2026-11-26: a later
decision reopens the visit until it is finalized again).

Revision ID: 0003
Revises: 0002
Created: 2026-11-26
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('visit_finalize',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('visit_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_decision_id', sa.Integer(), nullable=False),
    sa.Column('decisions', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['visit_id'], ['visit_check.visit_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('visit_id', 'last_decision_id', name='uq_visit_finalize_covers')
    )
    with op.batch_alter_table('visit_finalize', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visit_finalize_visit_id'), ['visit_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('visit_finalize', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visit_finalize_visit_id'))

    op.drop_table('visit_finalize')
