"""The patients' backup, backend/seed/patients.sql (owner, 2026-11-27: delete the patient files;
the backup lives in the repo). It holds exactly the tests' made-up patients, and loading it fills
a new database with them, safely twice.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from sqlmodel import Session

from artemis.patient.record import build_patient_context
from backend import patients_db, seed
from tests.api_fakes import memory_engine, read_patients

ROOT = Path(__file__).resolve().parents[1]
PG_URL = os.getenv("ARTEMIS_TEST_DATABASE_URL")
_WHEN = re.compile(r"'\d{4}-\d{2}-\d{2} [\d:.]+\+00:00'::timestamptz")


def _fixture_dump() -> str:
    engine = memory_engine()
    with Session(engine) as s:
        patients_db.import_records(s, read_patients(), origin="seed")
        return seed.dump(s)


def test_the_backup_holds_exactly_the_tests_patients():
    """The committed backup and the tests' patients can't drift apart (only the load time differs)."""
    committed = seed.SEED_SQL.read_text(encoding="utf-8")
    assert _WHEN.sub("<when>", committed) == _WHEN.sub("<when>", _fixture_dump())


def test_names_with_quotes_are_quoted_by_the_driver():
    engine = memory_engine()
    record = {**read_patients()[0], "patient_id": "Q1", "name": "Grace O'Brien'); DROP TABLE patient; --"}
    with Session(engine) as s:
        patients_db.import_records(s, [record], origin="seed")
        text = seed.dump(s)
    assert "'Grace O''Brien''); DROP TABLE patient; --'" in text


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
        seed.load(engine, text)
        seed.load(engine, text)
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
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")
