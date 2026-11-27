"""The clinic day in the database (plan 4C.3, owner 2026-11-27): each clinic day and its
appointments. An appointment is made only by adding a case; rows are only ever added.

Revision ID: 0005
Revises: 0004
Created: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('clinic_day',
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('clinic', sa.Text(), nullable=False),
    sa.Column('room', sa.Text(), nullable=False),
    sa.Column('clinician', sa.Text(), nullable=False),
    sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.PrimaryKeyConstraint('date')
    )
    op.create_table('appointment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('time', sqlmodel.sql.sqltypes.AutoString(length=5), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('booked_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['date'], ['clinic_day.date'], ),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('date', 'patient_id', name='uq_appointment_day_patient')
    )
    with op.batch_alter_table('appointment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_appointment_date'), ['date'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointment_patient_id'), ['patient_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('appointment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_appointment_patient_id'))
        batch_op.drop_index(batch_op.f('ix_appointment_date'))

    op.drop_table('appointment')
    op.drop_table('clinic_day')
