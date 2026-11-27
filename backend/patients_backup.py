"""The patients' and clinic days' backup (owner, 2026-11-27: "B, delete them" and "A, in the repo").

The database is the only copy of the app's patients; backend/seed/patients.sql is its backup, kept
in the repo so a new database (a fresh laptop, the website's end-to-end tests) can be filled. The
app never reads it. `dump` writes every patient row as SQL, values quoted by the Postgres driver.
It covers the patient tables and, since plan 4C.3, the clinic days and appointments. `load`
reads the file back as data, accepting only what `dump` writes, and inserts each row with
bound values in one save, safe to run again (a row already there is skipped). The file is never
run as commands: an edited backup can add patient and clinic rows, nothing else (security review,
2026-11-27). Commands: scripts/patients_backup.py make | load.
"""

from __future__ import annotations

import datetime
import json
import re
from typing import Any, Dict, List, Tuple

from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import JSON, Integer, func
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from backend import clinic_db, patients_db
from backend.patients_db import Patient
from backend.settings import PROJECT_ROOT

# Parents before the rows that point to them: the patient tables, then the clinic days and appointments.
TABLES = patients_db.TABLES + clinic_db.TABLES
SEED_SQL = PROJECT_ROOT / "backend" / "seed" / "patients.sql"
HEADER = (
    "-- The app's made-up patients and clinic days: the backup of those database tables (plan 4C.2, 4C.3).\n"
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
    """Every row of the patient and clinic-day tables as SQL inserts, parents first, each table in key order."""
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
    return "\n".join(lines) + "\n"


class BadBackup(ValueError):
    """The backup holds something `dump` never writes; nothing was loaded."""


_INSERT = re.compile(r'INSERT INTO "(\w+)" \(([^)]*)\) VALUES \(')
_VALUE = re.compile(r"\s*(?:(NULL)|(true|false)|(-?\d+)|(E?)'((?:[^']|'')*)'(?:::(date|timestamptz|jsonb))?)")
_END = ") ON CONFLICT DO NOTHING;"


def _text(e: str, body: str, at: int) -> str:
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c == "'":  # always doubled inside a literal
            out.append("'")
            i += 2
        elif c == "\\" and e:  # the driver doubles every backslash in an E'' string
            if body[i + 1:i + 2] != "\\":
                raise BadBackup(f"an escape the backup never writes, at character {at}")
            out.append("\\")
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _value(m: "re.Match[str]", at: int) -> Any:
    null, flag, number, e, body, cast = m.groups()
    if null:
        return None
    if flag:
        return flag == "true"
    if number:
        return int(number)
    value = _text(e, body, at)
    if cast == "date":
        return datetime.date.fromisoformat(value)
    if cast == "timestamptz":
        return datetime.datetime.fromisoformat(value)
    if cast == "jsonb":
        return json.loads(value)
    return value


def read_backup(text: str) -> List[Tuple[Any, Dict[str, Any]]]:
    """The rows a backup holds, as (table, values), read as data: only the statements `dump` writes
    are accepted (an insert into one of the backed-up tables with exactly its columns, or a
    comment). Anything else raises BadBackup, so an edited file can never run commands."""
    tables = {m.__tablename__: m.__table__ for m in TABLES}
    rows: List[Tuple[Any, Dict[str, Any]]] = []
    i = 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if text.startswith("--", i):
            end = text.find("\n", i)
            i = len(text) if end == -1 else end + 1
            continue
        head = _INSERT.match(text, i)
        if not head or head.group(1) not in tables:
            raise BadBackup(f"a statement the backup never writes, at character {i}")
        table = tables[head.group(1)]
        names = [n.strip().strip('"') for n in head.group(2).split(",")]
        if names != [c.name for c in table.columns]:
            raise BadBackup(f"columns that don't match the {table.name} table, at character {i}")
        i, values = head.end(), []
        for n, _ in enumerate(names):
            m = _VALUE.match(text, i)
            if not m:
                raise BadBackup(f"a value the backup never writes, at character {i}")
            values.append(_value(m, i))
            i = m.end()
            sep = ", " if n < len(names) - 1 else _END
            if not text.startswith(sep, i):
                raise BadBackup(f"a statement the backup never writes, at character {i}")
            i += len(sep)
        rows.append((table, dict(zip(names, values))))
    return rows


def load(engine: Engine, text: str) -> int:
    """Fill a database whose tables exist from a backup, in one save. The file is read as data and
    each row inserted with bound values, never run; a row whose key is already there is skipped,
    so it is safe to run again. Only into a new database, or one filled from this backup: rows are
    matched on their own numbers, so a database holding other patients is refused (BadBackup).
    Returns how many rows were added."""
    rows = read_backup(text)
    dialect = engine.dialect.name
    insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
    in_backup = {values["patient_id"] for table, values in rows if table.name == Patient.__tablename__}
    added = 0
    with engine.begin() as conn:
        others = set(conn.execute(select(Patient.patient_id)).scalars()) - in_backup
        if others:
            raise BadBackup(f"the database already holds {len(others)} patient(s) this backup doesn't; load it into a new database")
        for table, values in rows:
            key = next(iter(table.primary_key.columns))
            # An added row returns its key and a skipped one returns nothing: counted the same way on
            # Postgres and on the test database, whose drivers report row counts differently.
            returned = conn.execute(insert(table).values(**values).on_conflict_do_nothing().returning(key)).first()
            added += returned is not None
        if dialect == "postgresql":  # move each counter past the loaded rows
            for model in TABLES:
                key = next(iter(model.__table__.primary_key.columns))
                if isinstance(key.type, Integer):
                    top = conn.execute(select(func.max(key))).scalar() or 0
                    conn.execute(select(func.setval(func.pg_get_serial_sequence(model.__tablename__, key.name), top + 1, False)))
    return added
