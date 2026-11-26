"""Saved visit checks that say YELLOW now say AMBER (owner, 2026-11-26: "Amber everywhere").

A data change only; the tables stay as they are. Safe to run twice: the second run finds no
YELLOW rows. Going back down turns AMBER rows back into YELLOW.

Revision ID: 0002
Revises: 0001
Created: 2026-11-26
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE visit_check SET status = 'AMBER' WHERE status = 'YELLOW'")


def downgrade() -> None:
    op.execute("UPDATE visit_check SET status = 'YELLOW' WHERE status = 'AMBER'")
