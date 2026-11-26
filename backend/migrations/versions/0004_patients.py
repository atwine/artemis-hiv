"""Patients in the database (plan 4C.2, owner 2026-11-27): the patient and their medicines, past
ART, lab results and notes, earlier clinical notes and today's visit. Rows are only ever added.

Revision ID: 0004
Revises: 0003
Created: 2026-11-27
"""

from __future__ import annotations

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('patient',
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('sex', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True),
    sa.Column('age_years', sa.Integer(), nullable=True),
    sa.Column('art_regimen_as_entered', sa.Text(), nullable=True),
    sa.Column('complaints_symptoms', sa.Text(), nullable=False),
    sa.Column('examination_findings', sa.Text(), nullable=False),
    sa.Column('prior_history', sa.Text(), nullable=False),
    sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('patient_id')
    )
    with op.batch_alter_table('patient', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_patient_position'), ['position'], unique=True)

    op.create_table('art_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('regimen', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('art_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_art_history_patient_id'), ['patient_id'], unique=False)

    op.create_table('clinical_note',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('date', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
    sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('clinical_note', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_clinical_note_patient_id'), ['patient_id'], unique=False)

    op.create_table('encounter',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('visit_type', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('orders', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('med_changes', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('encounter', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_encounter_patient_id'), ['patient_id'], unique=False)

    op.create_table('lab_note',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('date', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lab_note', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lab_note_patient_id'), ['patient_id'], unique=False)

    op.create_table('lab_result',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('test', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('value', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
    sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
    sa.Column('source', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lab_result', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lab_result_patient_id'), ['patient_id'], unique=False)

    op.create_table('patient_medicine',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('patient_id', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['patient_id'], ['patient.patient_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('patient_medicine', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_patient_medicine_patient_id'), ['patient_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('patient_medicine', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_patient_medicine_patient_id'))

    op.drop_table('patient_medicine')
    with op.batch_alter_table('lab_result', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lab_result_patient_id'))

    op.drop_table('lab_result')
    with op.batch_alter_table('lab_note', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lab_note_patient_id'))

    op.drop_table('lab_note')
    with op.batch_alter_table('encounter', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_encounter_patient_id'))

    op.drop_table('encounter')
    with op.batch_alter_table('clinical_note', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_clinical_note_patient_id'))

    op.drop_table('clinical_note')
    with op.batch_alter_table('art_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_art_history_patient_id'))

    op.drop_table('art_history')
    with op.batch_alter_table('patient', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_patient_position'))

    op.drop_table('patient')
