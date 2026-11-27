"""The patients' backup, backend/seed/patients.sql (owner, 2026-11-27: delete the patient files;
the backup lives in the repo). It holds exactly the tests' made-up patients; loading it fills a new
database with them, safely twice; and it is read as data, so an edited file can't run commands
(security review, 2026-11-27).
"""

from __future__ import annotations

import datetime
import os
import re
from pathlib import Path

import pytest
from sqlmodel import Session

from artemis.patient.record import build_patient_context
from backend import clinic_db, patients_db
from backend import patients_backup as seed
from tests.api_fakes import memory_engine, read_clinic_day, read_patients

ROOT = Path(__file__).resolve().parents[1]
PG_URL = os.getenv("ARTEMIS_TEST_DATABASE_URL")
_WHEN = re.compile(r"'\d{4}-\d{2}-\d{2} [\d:.]+\+00:00'::timestamptz")
NOTE_COLUMNS = 'INSERT INTO "lab_note" ("id", "patient_id", "position", "date", "source", "text") VALUES '


def _fixture_dump() -> str:
    engine = memory_engine()
    with Session(engine) as s:
        patients_db.import_records(s, read_patients(), origin="seed")
        clinic_db.import_schedule(s, read_clinic_day(), origin="seed")
        return seed.dump(s)


def _empty_engine():
    """A database with the tables and no patients."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel

    memory_engine()  # registers the tables
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


def test_the_backup_holds_the_tests_patients():
    """Every one of the tests' made-up patients is in the backup, exactly. Cases added through the
    app and then backed up (`make`) may come after them; they don't fail this test (review, 2026-11-27)."""
    engine = _empty_engine()
    seed.load(engine, seed.SEED_SQL.read_text(encoding="utf-8"))
    fixtures = memory_engine()
    with Session(fixtures) as s:
        patients_db.import_records(s, read_patients(), origin="seed")
        expected = patients_db.load_all(s)
    with Session(engine) as s:
        backed_up = patients_db.load_all(s)
        demo = clinic_db.day_on(s, datetime.date(2026, 11, 26))
    assert backed_up[:len(expected)] == expected
    schedule = read_clinic_day()
    assert demo is not None and demo[0].clinician == schedule["clinician"]
    assert [(a.time, a.patient_id, a.name) for a in demo[1]] == [
        (b["time"], b["patient_id"], b.get("name")) for b in schedule["appointments"]]


def test_dump_then_load_gives_the_same_backup():
    engine = _empty_engine()
    seed.load(engine, _fixture_dump())
    with Session(engine) as s:
        again = seed.dump(s)
    assert _WHEN.sub("<when>", again) == _WHEN.sub("<when>", _fixture_dump())


def test_a_backup_is_not_loaded_into_a_database_holding_other_patients():
    engine = memory_engine()
    with Session(engine) as s:
        patients_db.import_records(s, [{**read_patients()[0], "patient_id": "OTHER"}], origin="seed")
    with pytest.raises(seed.BadBackup, match="1 patient"):
        seed.load(engine, seed.SEED_SQL.read_text(encoding="utf-8"))
    with Session(engine) as s:
        assert [p["patient_id"] for p in patients_db.load_all(s)] == ["OTHER"]


def test_loading_the_backup_gives_the_tests_patients_and_is_safe_twice():
    engine = _empty_engine()
    text = seed.SEED_SQL.read_text(encoding="utf-8")
    assert seed.load(engine, text) > 0
    assert seed.load(engine, text) == 0
    with Session(engine) as s:
        back = {p["patient_id"]: p for p in patients_db.load_all(s)}
    expected = read_patients()
    assert list(back) == [p["patient_id"] for p in expected]
    for patient in expected:
        assert build_patient_context(back[patient["patient_id"]]) == build_patient_context(patient)


def test_names_with_quotes_are_quoted_by_the_driver():
    engine = memory_engine()
    record = {**read_patients()[0], "patient_id": "Q1", "name": "Grace O'Brien'); DROP TABLE patient; --"}
    with Session(engine) as s:
        patients_db.import_records(s, [record], origin="seed")
        text = seed.dump(s)
    assert "'Grace O''Brien''); DROP TABLE patient; --'" in text


AWKWARD = "O'Brien \\ back\\slash $$ $tag$ ; -- E'\\x27' \r\n\t   ✓ " + "x" * 5000


def test_awkward_text_comes_back_exactly():
    engine = memory_engine()
    record = {**read_patients()[0], "patient_id": "Q2", "name": AWKWARD}
    record["today_encounter"] = {**record["today_encounter"], "orders": [{"note": AWKWARD}]}
    with Session(engine) as s:
        patients_db.import_records(s, [record], origin="seed")
        text = seed.dump(s)
    fresh = _empty_engine()
    seed.load(fresh, text)
    with Session(fresh) as s:
        back = patients_db.load_all(s)[0]
    assert back["name"] == AWKWARD
    assert back["today_encounter"]["orders"] == [{"note": AWKWARD}]


@pytest.mark.parametrize("extra", [
    "COPY patient FROM PROGRAM 'id';",
    "DROP TABLE patient;",
    """INSERT INTO "visit_check" ("visit_id") VALUES ('x') ON CONFLICT DO NOTHING;""",
    """INSERT INTO "lab_note" ("id", "patient_id") VALUES (900, 'P001') ON CONFLICT DO NOTHING;""",
    NOTE_COLUMNS + "(900, 'P001', 0, NULL, NULL, (SELECT pg_read_file('/etc/passwd'))) ON CONFLICT DO NOTHING;",
    NOTE_COLUMNS + "(900, 'P001', 0, NULL, NULL, 'x') ON CONFLICT DO NOTHING; COPY patient FROM PROGRAM 'id';",
    NOTE_COLUMNS + "(900, 'P001', 0, NULL, NULL, E'\\x27') ON CONFLICT DO NOTHING;",
])
def test_an_edited_backup_is_refused_and_loads_nothing(extra):
    engine = _empty_engine()
    text = seed.SEED_SQL.read_text(encoding="utf-8") + extra + "\n"
    with pytest.raises(seed.BadBackup):
        seed.load(engine, text)
    with Session(engine) as s:
        assert patients_db.load_all(s) == []


@pytest.mark.skipif(not PG_URL, reason="set ARTEMIS_TEST_DATABASE_URL to a throwaway Postgres database to run this")
def test_loading_the_backup_fills_a_new_database_safely_twice():
    from alembic import command
    from alembic.config import Config
    from sqlmodel import create_engine

    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", PG_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(PG_URL)
    try:
        text = seed.SEED_SQL.read_text(encoding="utf-8")
        assert seed.load(engine, text) > 0
        assert seed.load(engine, text) == 0
        with Session(engine) as s:
            back = {p["patient_id"]: p for p in patients_db.load_all(s)}
        expected = read_patients()
        assert list(back) == [p["patient_id"] for p in expected]
        for patient in expected:
            assert build_patient_context(back[patient["patient_id"]]) == build_patient_context(patient)
        # The counters moved past the loaded rows: a new case gets fresh numbers.
        patients_db.add(engine, {**expected[0], "patient_id": "P100"})
        with Session(engine) as s:
            assert [p["patient_id"] for p in patients_db.load_all(s)][-1] == "P100"
        # An edited backup is refused on Postgres too, before anything runs.
        with pytest.raises(seed.BadBackup):
            seed.load(engine, text + "COPY patient FROM PROGRAM 'id';\n")
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")
