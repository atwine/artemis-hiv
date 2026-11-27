"""Visit records in the database (plan item 4.5).

Most tests use SQLite in memory or in a temporary folder, so they run anywhere (and on GitHub).
test_on_real_postgres runs only when ARTEMIS_TEST_DATABASE_URL points at a throwaway Postgres
database; it creates the tables there with Alembic and drops them at the end.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine

from backend import records
from backend.records import VisitCheck
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
        with Session(engine) as s:
            records.save_check(s, _checks(), origin="api")
            records.add_decisions(s, "v1", _finalized()["decisions"], saved_at="2026-11-20T08:05:00+00:00")
            records.add_finalize(s, "v1", _finalized()["decisions"], finalized_at="2026-11-20T08:06:00+00:00")
        with Session(engine) as s:
            assert records.entry_from_check(s.get(VisitCheck, "v1")) == _checks()
            assert records.latest_decisions(s, "v1")["a1"].action == "Acknowledge"
            assert records.finalized_at(s, "v1") == "2026-11-20T08:06:00+00:00"
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
