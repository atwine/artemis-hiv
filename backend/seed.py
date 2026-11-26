"""The patients' backup (owner, 2026-11-27: "B, delete them" and "A, in the repo").

The database is the only copy of the app's patients; backend/seed/patients.sql is its backup, kept
in the repo so a new database (a fresh laptop, the website's end-to-end tests) can be filled. The
app never reads it. `dump` writes every patient row as SQL; `load` runs it in one save and is safe
to run again (a row already there is skipped). Values are quoted by the Postgres driver, never by
hand. Commands: scripts/patients_backup.py make | load.
"""

from __future__ import annotations

import datetime
from typing import Any

from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import JSON, Integer
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from backend.patients_db import TABLES
from backend.settings import PROJECT_ROOT

SEED_SQL = PROJECT_ROOT / "backend" / "seed" / "patients.sql"
HEADER = (
    "-- The app's made-up patients: the backup of the database's patient tables (plan 4C.2).\n"
    "-- Made by `python scripts/patients_backup.py make`; loaded into a new database by\n"
    "-- `python scripts/patients_backup.py load` after `alembic upgrade head`. The app never reads it.\n"
)


def _literal(value: Any, column: Any) -> sql.Composable:
    if value is not None and isinstance(column.type, JSON):
        return sql.Literal(Jsonb(value))
    if isinstance(value, datetime.datetime) and value.tzinfo is None:  # SQLite hands them back without a zone
        value = value.replace(tzinfo=datetime.timezone.utc)
    return sql.Literal(value)


def dump(session: Session) -> str:
    """Every row of the patient tables as SQL, parents first, each table in key order, then each
    numbered table's counter moved past its rows so the next added case gets a fresh number."""
    lines = [HEADER]
    for model in TABLES:
        table = model.__table__
        key = next(iter(table.primary_key.columns))
        names = [c.name for c in table.columns]
        for row in session.exec(select(model).order_by(key)).all():
            lines.append(sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING;").format(
                sql.Identifier(table.name), sql.SQL(", ").join(map(sql.Identifier, names)),
                sql.SQL(", ").join(_literal(getattr(row, n), table.c[n]) for n in names),
            ).as_string())
    for model in TABLES:
        table = model.__table__
        key = next(iter(table.primary_key.columns))
        if isinstance(key.type, Integer):
            lines.append(sql.SQL("SELECT setval(pg_get_serial_sequence({t}, {k}), (SELECT COALESCE(MAX({ki}), 0) + 1 FROM {ti}), false);").format(
                t=sql.Literal(table.name), k=sql.Literal(key.name), ki=sql.Identifier(key.name), ti=sql.Identifier(table.name),
            ).as_string())
    return "\n".join(lines) + "\n"


def load(engine: Engine, text: str) -> None:
    """Run a backup on a Postgres database whose tables exist, in one save."""
    with engine.begin() as conn:
        # The driver runs a whole script when it is given no parameters.
        conn.connection.driver_connection.execute(text)
