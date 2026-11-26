"""Visit records: visit_check (one row per run of the checks) and alert_decision (one row per decision).

Revision ID: 0001
Revises: (first)
Created: 2026-11-26 15:12:56.176431
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('visit_check',
    sa.Column('visit_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('visit_date', sqlmodel.sql.sqltypes.AutoString(length=10), nullable=False),
    sa.Column('saved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('model', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True),
    sa.Column('app_version', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('ai_review', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('ai_review_ran', sa.Boolean(), nullable=False),
    sa.Column('alerts', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('results', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
    sa.Column('screening_debug', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
    sa.Column('patient_summary', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
    sa.Column('agentic_enabled', sa.Boolean(), nullable=False),
    sa.Column('plan', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=True),
    sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.PrimaryKeyConstraint('visit_id')
    )
    with op.batch_alter_table('visit_check', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visit_check_patient_id'), ['patient_id'], unique=False)

    op.create_table('alert_decision',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('visit_id', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('alert_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('title', sa.Text(), nullable=False),
    sa.Column('severity', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True),
    sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('comment', sa.Text(), nullable=False),
    sa.Column('saved_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['visit_id'], ['visit_check.visit_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('alert_decision', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alert_decision_visit_id'), ['visit_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('alert_decision', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alert_decision_visit_id'))

    op.drop_table('alert_decision')
    with op.batch_alter_table('visit_check', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visit_check_patient_id'))

    op.drop_table('visit_check')
