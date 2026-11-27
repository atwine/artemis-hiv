"""Visit records in the database (plan item 4.5).

Most tests use SQLite in memory or in a temporary folder, so they run anywhere (and on GitHub).
test_on_real_postgres runs only when ARTEMIS_TEST_DATABASE_URL points at a throwaway Postgres
database; it creates the tables there with Alembic and drops them at the end.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from artemis import visit_record
from backend import records
from backend.records import AlertDecision, VisitCheck
from tests.api_fakes import memory_engine

ROOT = Path(__file__).resolve().parents[1]


def _checks(visit_id="v1", patient_id="P001", saved_at="2026-11-20T08:00:00+00:00"):
    return {
        "event": "checks_run", "visit_id": visit_id, "patient_id": patient_id, "visit_date": "2026-01-22",
        "saved_at": saved_at, "note": "Routine follow-up.", "model": "llama", "app_version": "abc123",
        "status": "AMBER", "ai_review": "ok", "ai_review_ran": True,
        "alerts": [{"alert_id": "a1", "title": "T", "message": "M", "evidence": {}, "query_hint": "", "source": "rule", "severity": None}],
        "results": [{"retrieved": [], "explanation": {"text": "E", "used_llm": False}}],
        "screening_debug": {"parse_status": "parsed_nonempty"}, "patient_summary": {"x": 1},
        "agentic_enabled": False, "plan": None,
    }


def _finalized(visit_id="v1", patient_id="P001", saved_at="2026-11-20T08:05:00+00:00", action="Acknowledge"):
    return {
        "event": "finalized", "visit_id": visit_id, "patient_id": patient_id, "saved_at": saved_at,
        "decisions": [{"alert_id": "a1", "source": "rule", "title": "T", "severity": None, "action": action, "reason": "", "comment": ""}],
    }


def _folder(tmp_path, *entries):
    folder = tmp_path / "visit_records"
    for e in entries:
        visit_record.append_entry(folder, e)
    return folder


def _counts(engine):
    with Session(engine) as s:
        return len(s.exec(select(VisitCheck)).all()), len(s.exec(select(AlertDecision)).all())


def test_import_the_files(tmp_path):
    engine = memory_engine()
    folder = _folder(tmp_path, _checks(), _finalized())
    with Session(engine) as s:
        report = records.import_folder(s, folder)
    assert report == {"checks_added": 1, "decisions_added": 1, "finalized_added": 1, "already_there": 0, "unreadable_lines": 0, "skipped": 0}
    with Session(engine) as s:
        row = s.get(VisitCheck, "v1")
        assert row.note == "Routine follow-up."
        assert row.origin == "file import"
        assert row.alerts[0]["alert_id"] == "a1"
        d = s.exec(select(AlertDecision)).one()
        assert (d.visit_id, d.alert_id, d.action) == ("v1", "a1", "Acknowledge")


def test_import_twice_adds_nothing_the_second_time(tmp_path):
    engine = memory_engine()
    folder = _folder(tmp_path, _checks(), _finalized(), _finalized(saved_at="2026-11-20T09:00:00+00:00", action="Override"))
    with Session(engine) as s:
        records.import_folder(s, folder)
    with Session(engine) as s:
        report = records.import_folder(s, folder)
    assert report["checks_added"] == 0 and report["decisions_added"] == 0
    assert report["already_there"] == 3
    assert _counts(engine) == (1, 2)


def test_import_counts_what_it_cannot_use(tmp_path):
    engine = memory_engine()
    folder = _folder(tmp_path, _checks())
    path = next(folder.glob("*.jsonl"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{half a line\n")
        fh.write(json.dumps(_finalized(visit_id=None)) + "\n")  # an older Finalize with no visit id
        fh.write(json.dumps(_finalized(visit_id="never-ran")) + "\n")  # a Finalize for a run not in the files
    with Session(engine) as s:
        report = records.import_folder(s, folder)
    assert report["checks_added"] == 1
    assert report["unreadable_lines"] == 1
    assert report["skipped"] == 2
    assert _counts(engine) == (1, 0)


def test_import_leaves_the_files_alone(tmp_path):
    folder = _folder(tmp_path, _checks(), _finalized())
    before = {p.name: p.read_bytes() for p in folder.iterdir()}
    with Session(memory_engine()) as s:
        records.import_folder(s, folder)
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


def test_import_of_a_missing_folder_is_empty(tmp_path):
    with Session(memory_engine()) as s:
        assert records.import_folder(s, tmp_path / "none")["checks_added"] == 0


def test_saved_check_reads_back_the_same(tmp_path):
    engine = memory_engine()
    entry = _checks()
    with Session(engine) as s:
        records.save_check(s, entry, origin="api")
    with Session(engine) as s:
        row = s.get(VisitCheck, "v1")
        back = records.entry_from_check(row)
    assert back == entry


def test_dates_and_odd_values_are_stored_as_text(tmp_path):
    import datetime

    engine = memory_engine()
    entry = _checks()
    entry["alerts"][0]["evidence"] = {"last_lab": datetime.date(2024, 10, 1)}
    with Session(engine) as s:
        records.save_check(s, entry, origin="api")
    with Session(engine) as s:
        assert s.get(VisitCheck, "v1").alerts[0]["evidence"] == {"last_lab": "2024-10-01"}


def test_latest_decision_counts(tmp_path):
    engine = memory_engine()
    with Session(engine) as s:
        records.save_check(s, _checks(), origin="api")
        records.add_decisions(s, "v1", _finalized()["decisions"], saved_at="2026-11-20T08:05:00+00:00")
        records.add_decisions(s, "v1", _finalized(action="Override")["decisions"], saved_at="2026-11-20T08:06:00+00:00")
    with Session(engine) as s:
        latest = records.latest_decisions(s, "v1")
    assert latest["a1"].action == "Override"


def _alembic_config(url: str):
    from alembic.config import Config

    cfg = Config(str(ROOT / "backend" / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_migrations_build_exactly_the_tables_in_the_code(tmp_path):
    """Alembic's history ends at the tables the models describe: nothing missing, nothing extra."""
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    command.upgrade(_alembic_config(url), "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == []
    command.downgrade(_alembic_config(url), "base")
    with engine.connect() as conn:
        assert set(engine.dialect.get_table_names(conn)) <= {"alembic_version"}


PG_URL = os.getenv("ARTEMIS_TEST_DATABASE_URL")


@pytest.mark.skipif(not PG_URL, reason="set ARTEMIS_TEST_DATABASE_URL to a throwaway Postgres database to run this")
def test_on_real_postgres(tmp_path):
    from alembic import command
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    cfg = _alembic_config(PG_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(PG_URL)
    try:
        with engine.connect() as conn:
            assert compare_metadata(MigrationContext.configure(conn), SQLModel.metadata) == []
        folder = _folder(tmp_path, _checks(), _finalized())
        with Session(engine) as s:
            records.import_folder(s, folder)
        with Session(engine) as s:
            assert records.import_folder(s, folder)["already_there"] == 2
            assert records.entry_from_check(s.get(VisitCheck, "v1")) == _checks()
            assert records.latest_decisions(s, "v1")["a1"].action == "Acknowledge"
        # "Compare plans" (migration 0006): plans are added, the latest one is shown.
        import datetime as _dt

        at = _dt.datetime(2026, 11, 27, 9, tzinfo=_dt.timezone.utc)
        with Session(engine) as s:
            records.save_plan(s, records.VisitPlan(visit_id="v1", made_at=at, model="m", outcome="failed",
                                                   plan_text=None, issues=["no_reply"], error_type="RuntimeError"))
            records.save_plan(s, records.VisitPlan(visit_id="v1", made_at=at + _dt.timedelta(minutes=1), model="m",
                                                   outcome="made", plan_text='{"problems": []}', issues=["cut_off"]))
        with Session(engine) as s:
            latest = records.latest_plan(s, "v1")
            assert (latest.outcome, latest.issues, latest.plan_text) == ("made", ["cut_off"], '{"problems": []}')
            assert records.latest_plan(s, "nope") is None
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")


def test_an_older_file_that_says_yellow_is_stored_as_amber(tmp_path):
    engine = memory_engine()
    old = _checks()
    old["status"] = "YELLOW"
    with Session(engine) as s:
        records.import_folder(s, _folder(tmp_path, old))
    with Session(engine) as s:
        assert s.get(VisitCheck, "v1").status == "AMBER"


def test_the_amber_migration_renames_saved_rows_and_is_safe_twice(tmp_path):
    """Alembic 0002: rows saved as YELLOW become AMBER; running it again changes nothing;
    going back down restores YELLOW."""
    from alembic import command
    from sqlalchemy import text

    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = _alembic_config(url)
    command.upgrade(cfg, "0001")
    engine = create_engine(url)
    row = records.check_from_entry(_checks(), origin="api")
    with engine.begin() as conn:
        for vid, status in [("v1", "YELLOW"), ("v2", "RED"), ("v3", "YELLOW")]:
            values = {**row.model_dump(), "visit_id": vid, "status": status}
            conn.execute(VisitCheck.__table__.insert().values(**values))

    def statuses():
        with engine.connect() as conn:
            return dict(conn.execute(text("SELECT visit_id, status FROM visit_check ORDER BY visit_id")).all())

    command.upgrade(cfg, "head")
    assert statuses() == {"v1": "AMBER", "v2": "RED", "v3": "AMBER"}
    command.downgrade(cfg, "0001")
    command.upgrade(cfg, "head")  # a second run
    assert statuses() == {"v1": "AMBER", "v2": "RED", "v3": "AMBER"}
    command.downgrade(cfg, "0001")
    assert statuses() == {"v1": "YELLOW", "v2": "RED", "v3": "YELLOW"}
    engine.dispose()


def test_a_finalized_file_visit_is_finalized_in_the_database(tmp_path):
    from backend.records import VisitFinalize

    engine = memory_engine()
    folder = _folder(tmp_path, _checks(), _finalized())
    with Session(engine) as s:
        records.import_folder(s, folder)
        records.import_folder(s, folder)  # a second run adds nothing
    with Session(engine) as s:
        rows = s.exec(select(VisitFinalize)).all()
        assert len(rows) == 1
        assert rows[0].visit_id == "v1"
        assert records.iso(rows[0].finalized_at) == "2026-11-20T08:05:00+00:00"
        assert records.finalized_at(s, "v1") == "2026-11-20T08:05:00+00:00"


def test_a_later_decision_in_the_files_reopens_the_visit(tmp_path):
    """Two Finalize lines: the later one counts, and the visit is finalized as of it."""
    engine = memory_engine()
    folder = _folder(tmp_path, _checks(), _finalized(), _finalized(saved_at="2026-11-20T09:00:00+00:00", action="Override"))
    with Session(engine) as s:
        records.import_folder(s, folder)
        assert records.finalized_at(s, "v1") == "2026-11-20T09:00:00+00:00"
        records.add_decisions(s, "v1", _finalized()["decisions"], saved_at="2026-11-20T09:30:00+00:00")
        assert records.finalized_at(s, "v1") is None
