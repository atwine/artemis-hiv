"""Patients in the database (plan 4C.2, owner 2026-11-27: "A, keep the rules").

The made-up patients are loaded once from the seed files into tables (backend/patients_db.py);
the backend reads and adds patients only there. Proof the move changes nothing: every seed patient
read back from the database gives the same patient context, the same screen record and the same
visit check as the same patient read from its file. Tests use an in-memory database and never
write Data/.
"""

from __future__ import annotations

import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from artemis.patient.labs import read_lab_entries, read_lab_notes
from artemis.patient.record import build_patient_context
from backend import patients_db
from tests.api_fakes import FakeModel, fake_search, memory_engine, read_patients, replies_for

LOCAL = {"Origin": "http://localhost:3000"}
SEED = read_patients()


def _loaded_engine():
    engine = memory_engine()
    with Session(engine) as s:
        patients_db.import_records(s, copy.deepcopy(SEED), origin="seed")
    return engine


@pytest.fixture(scope="module")
def engine():
    return _loaded_engine()


def _back(engine):
    with Session(engine) as s:
        return {p["patient_id"]: p for p in patients_db.load_all(s)}


def test_every_seed_patient_is_loaded_in_file_order(engine):
    assert list(_back(engine)) == [p["patient_id"] for p in SEED]


@pytest.mark.parametrize("patient", SEED, ids=lambda p: p["patient_id"])
def test_a_patient_read_back_gives_the_same_context(engine, patient):
    back = _back(engine)[patient["patient_id"]]
    assert build_patient_context(back) == build_patient_context(patient)
    assert read_lab_entries(back) == read_lab_entries(patient)
    assert read_lab_notes(back) == read_lab_notes(patient)


def test_the_answer_keys_stay_out_of_the_database(engine):
    assert any("expected_demo_outcome" in p for p in SEED)
    assert not any("expected_demo_outcome" in p for p in _back(engine).values())


def _client(patients, engine, added=None):
    from backend.main import create_app
    from backend.services import Services
    from backend.settings import Settings

    search = fake_search()
    box = {}
    services = Services(patients=patients, search=lambda: search, model_client=lambda: box["model"], engine=engine,
                        app_version="test")
    return TestClient(create_app(settings=Settings(), services=services), base_url="http://localhost"), box


@pytest.mark.parametrize("patient", SEED, ids=lambda p: p["patient_id"])
def test_the_screen_and_the_visit_check_are_the_same_from_the_database(patient):
    """The API before the move (patients from the files) and after (from the database)."""
    pid = patient["patient_id"]
    db = _loaded_engine()

    def from_db():
        with Session(db) as s:
            return patients_db.load_all(s)

    replies = []
    for patients, engine in ((lambda: copy.deepcopy(SEED), memory_engine()), (from_db, db)):
        client, box = _client(patients, engine)
        box["model"] = FakeModel(replies_for(pid))
        detail = client.get(f"/api/patients/{pid}", headers=LOCAL)
        listed = client.get("/api/patients", headers=LOCAL)
        check = client.post(f"/api/patients/{pid}/visits", json={"note": patient["today_encounter"]["note"]}, headers=LOCAL)
        assert detail.status_code == listed.status_code == check.status_code == 200, check.text
        # Each card's ids start with the new visit's random id: the same placeholder for both.
        visit = json.loads(check.text.replace(check.json()["visit_id"], "<visit>"))
        replies.append((detail.json(), listed.json(), visit["cards"],
                        {k: visit[k] for k in ("status", "ai_review", "plan", "banners")}, box["model"].calls))
    assert replies[1] == replies[0]


def test_loading_the_seed_again_adds_nothing(engine):
    with Session(engine) as s:
        before = {t.__tablename__: len(s.exec(select(t)).all()) for t in patients_db.TABLES}
        added = patients_db.import_records(s, copy.deepcopy(SEED), origin="seed")
        after = {t.__tablename__: len(s.exec(select(t)).all()) for t in patients_db.TABLES}
    assert added == 0
    assert after == before


def test_a_field_the_tables_have_no_place_for_is_refused_not_dropped():
    engine = memory_engine()
    with Session(engine) as s, pytest.raises(patients_db.UnplacedField, match="favourite_colour"):
        patients_db.import_records(s, [{**copy.deepcopy(SEED[0]), "patient_id": "X1", "favourite_colour": "blue"}],
                                   origin="seed")
    with Session(engine) as s:
        assert patients_db.load_all(s) == []


def test_a_lab_result_with_no_readable_date_is_refused_not_dropped():
    record = copy.deepcopy(SEED[0])
    record["patient_id"] = "X2"
    record["labs"]["cd4"] = [{"date": "last spring", "value": "350", "unit": "cells/uL"}]
    with Session(memory_engine()) as s, pytest.raises(patients_db.UnplacedField, match="cd4"):
        patients_db.import_records(s, [record], origin="seed")


def test_adding_a_case_is_one_save_and_a_used_id_is_refused():
    engine = _loaded_engine()
    new = {"patient_id": "P100", "art_regimen_current": ["TDF", "3TC", "DTG"], "other_medications": [],
           "visits": [], "labs": {"cd4": [{"date": "2026-11-20", "value": "350", "unit": "cells/uL", "source": "today"}]},
           "today_encounter": {"date": "2026-11-27", "note": "", "orders": [], "med_changes": []},
           "intake": {"complaints_symptoms": "", "examination_findings": "", "prior_history": ""},
           "age_years": None, "sex": None}
    patients_db.add(engine, new)
    with pytest.raises(patients_db.PatientExists):
        patients_db.add(engine, {**new, "labs": {}})
    with Session(engine) as s:
        back = {p["patient_id"]: p for p in patients_db.load_all(s)}
        rows = s.exec(select(patients_db.LabResult).where(patients_db.LabResult.patient_id == "P100")).all()
    assert list(back)[-1] == "P100"
    assert back["P100"]["labs"] == new["labs"]
    assert len(rows) == 1  # the refused second add left nothing behind


def test_a_case_added_through_the_api_is_in_the_database(api):
    r = api.client.post("/api/patients", json={"patient_id": "P100", "art_regimen": ["TLD"], "todays_note": "New.",
                                                    "appointment_time": "11:30"},
                        headers=LOCAL)
    assert r.status_code == 201, r.text
    with Session(api.engine) as s:
        back = {p["patient_id"]: p for p in patients_db.load_all(s)}
    assert back["P100"]["today_encounter"]["note"] == "New."
    assert api.client.get("/api/patients/P100", headers=LOCAL).json()["art_regimen_current"] == ["TDF", "3TC", "DTG"]


def test_without_a_database_the_patient_routes_say_so(api):
    api.services.engine = None
    for url in ("/api/patients", "/api/patients/P001", "/api/clinic-day"):
        r = api.client.get(url, headers=LOCAL)
        assert r.status_code == 503, (url, r.text)


PG_URL = __import__("os").getenv("ARTEMIS_TEST_DATABASE_URL")


@pytest.mark.skipif(not PG_URL, reason="set ARTEMIS_TEST_DATABASE_URL to a throwaway Postgres database to run this")
def test_the_patients_on_real_postgres():
    """Postgres checks each link between tables as a row goes in, and stores dates and lists its own
    way: the same round trip, the same rerun and the same refused id as on the test database."""
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlmodel import create_engine

    cfg = Config(str(Path(__file__).resolve().parents[1] / "backend" / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", PG_URL)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    engine = create_engine(PG_URL)
    try:
        with Session(engine) as s:
            assert patients_db.import_records(s, copy.deepcopy(SEED), origin="seed") == len(SEED)
            assert patients_db.import_records(s, copy.deepcopy(SEED), origin="seed") == 0
            back = {p["patient_id"]: p for p in patients_db.load_all(s)}
        assert list(back) == [p["patient_id"] for p in SEED]
        for patient in SEED:
            assert build_patient_context(back[patient["patient_id"]]) == build_patient_context(patient)
        with pytest.raises(patients_db.PatientExists):
            patients_db.add(engine, copy.deepcopy(SEED[0]))
    finally:
        engine.dispose()
        command.downgrade(cfg, "base")


def test_two_new_cases_taking_the_same_list_position_are_both_saved(monkeypatch):
    """Review, 2026-11-27: two different new cases added at the same moment read the same next
    position; the second tries the next one instead of failing."""
    engine = _loaded_engine()
    real = patients_db._next_position
    stale = {"left": 1}

    def racing(session):
        if stale["left"]:
            stale["left"] -= 1
            return real(session) - 1  # the position the other case has just taken
        return real(session)

    monkeypatch.setattr(patients_db, "_next_position", racing)
    patients_db.add(engine, {**copy.deepcopy(SEED[0]), "patient_id": "P201"})
    with Session(engine) as s:
        assert [p["patient_id"] for p in patients_db.load_all(s)][-1] == "P201"


@pytest.mark.parametrize("change, field", [
    ({"labs": {"creatinine": [{"date": "2025-01-01", "value_umol_per_l": 80, "note": "haemolysed"}]}}, "note"),
    ({"labs": {"creatinine": [{"date": "2025-01-01", "value": "80", "unit": "umol/L", "value_umol_per_l": 80}]}}, "value_umol_per_l"),
    ({"intake": {"complaints_symptoms": None, "examination_findings": "", "prior_history": ""}}, "complaints_symptoms"),
    ({"other_medications": [None]}, "other_medications"),
])
def test_odd_parts_of_a_record_are_refused_not_dropped(change, field):
    record = {**copy.deepcopy(SEED[0]), "patient_id": "X3", **change}
    with Session(memory_engine()) as s, pytest.raises(patients_db.UnplacedField, match=field):
        patients_db.import_records(s, [record], origin="seed")
