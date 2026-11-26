"""The backend's routes, called the way the Next.js frontend will call them (plan items 4.2, 4.4).

The model and the guideline search are stand-ins (tests/api_fakes.py) and the database is in
memory, so nothing is downloaded, no index is built and no money is spent.
"""

from __future__ import annotations

import copy

import pytest
from sqlmodel import Session, select

from artemis.visit import AnalysisOptions, run_visit_analysis
from tests.api_fakes import FakeModel, fake_search, read_patients, replies_for

LOCAL = {"Origin": "http://localhost:3000"}
P001_NOTE = "Routine follow-up. No issues."
OVERRIDE_REASONS = ["Already addressed", "Not applicable", "Will address later", "Patient declined", "Other"]


def _check(api, patient_id="P001", **body):
    body.setdefault("note", P001_NOTE)
    return api.client.post(f"/api/patients/{patient_id}/visits", json=body, headers=LOCAL)


def _decide(api, visit_id, *decisions):
    return api.client.post(f"/api/visits/{visit_id}/decisions", json={"decisions": list(decisions)}, headers=LOCAL)


# Patients


def test_health(api):
    r = api.client.get("/api/health", headers=LOCAL)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_patient_list_has_every_demo_patient_in_file_order(api):
    r = api.client.get("/api/patients", headers=LOCAL)
    assert r.status_code == 200
    assert [p["patient_id"] for p in r.json()] == [str(p["patient_id"]) for p in read_patients()]
    first = r.json()[0]
    assert first == {
        "patient_id": "P001", "name": "John Doe", "sex": "M", "age_years": 34,
        "art_regimen_current": ["TDF", "3TC", "DTG"], "visit_date": "2026-01-22",
    }


def test_patient_record(api):
    r = api.client.get("/api/patients/P001", headers=LOCAL)
    assert r.status_code == 200
    body = r.json()
    assert body["patient_id"] == "P001"
    assert body["labs"]["creatinine"] == [{"date": "2024-10-01", "value_umol_per_l": 88}]
    assert body["today_encounter"]["note"] == P001_NOTE
    # The answer key stays out of what the screen gets.
    assert "expected_demo_outcome" not in body


def test_patient_id_with_a_space(api):
    r = api.client.get("/api/patients/Kintu-Test 001", headers=LOCAL)
    assert r.status_code == 200
    assert r.json()["patient_id"] == "Kintu-Test 001"


def test_unknown_patient_is_404(api):
    assert api.client.get("/api/patients/NOPE", headers=LOCAL).status_code == 404


def test_a_bad_patient_record_is_reported_not_skipped(api):
    api.services.patients = lambda: [{"patient_id": "P1", "today_encounter": {"date": "not a date"}}]
    r = api.client.get("/api/patients", headers=LOCAL)
    assert r.status_code == 500
    assert r.json() == {"detail": "The patient list could not be read."}


# Visit check


def test_visit_check_is_the_same_analysis_as_the_app(api):
    """The route is a thin shell: same alerts and status as calling run_visit_analysis directly."""
    r = _check(api)
    assert r.status_code == 200, r.text
    body = r.json()

    patient = next(p for p in read_patients() if p["patient_id"] == "P001")
    direct = run_visit_analysis(
        patient=copy.deepcopy(patient), today_note=P001_NOTE, rag=fake_search(),
        llm_client=FakeModel(replies_for("P001")), options=AnalysisOptions(top_k=5, use_llm=True, agentic=False),
    )
    assert body["status"] == direct.status
    assert body["ai_review"] == direct.screening_outcome == "ok"
    assert [c["uuid"] for c in body["cards"]] == [a.alert_id for a in direct.alerts]
    assert body["patient_id"] == "P001"
    assert body["visit_date"] == "2026-01-22"
    assert body["model"] == "fake-model"
    assert body["record_saved"] is True
    assert body["plan"] is None


def test_cards_take_the_cds_hooks_shape(api):
    cards = _check(api).json()["cards"]
    assert cards
    for card in cards:
        assert set(card) >= {"uuid", "summary", "detail", "indicator", "source", "suggestions", "overrideReasons", "selectionBehavior", "extension"}
        assert 0 < len(card["summary"]) <= 140
        assert card["indicator"] in {"info", "warning", "critical"}
        assert card["source"]["label"] in {"ARTEMIS fixed rule", "ARTEMIS AI review"}
        assert [o["display"] for o in card["overrideReasons"]] == OVERRIDE_REASONS
        assert all(o["code"] and o["system"] for o in card["overrideReasons"])
        for s in card["suggestions"]:
            assert s["label"] and s["uuid"] and s["actions"] == []
        assert card["selectionBehavior"] == "at-most-one"


def test_rule_card(api):
    card = next(c for c in _check(api).json()["cards"] if c["uuid"] == "tdf_creatinine_overdue")
    assert card["summary"] == "Creatinine monitoring overdue while on TDF"
    assert card["detail"].startswith("Creatinine last recorded")
    assert card["indicator"] == "warning"  # no severity on a rule alert counts as moderate
    assert card["source"] == {"label": "ARTEMIS fixed rule", "topic": {"code": "rule", "display": "Fixed rule check", "system": "https://github.com/atwine/artemis-hiv/alert-source"}}
    assert card["extension"]["kind"] == "rule"
    assert card["extension"]["severity"] is None
    # A rule alert's passages come from a search for it.
    assert len(card["extension"]["passages"]) == 5


def test_ai_card_quotes_the_passages_it_cited(api):
    card = next(c for c in _check(api).json()["cards"] if c["uuid"] == "P001_001")
    assert card["indicator"] == "warning"  # moderate
    assert card["extension"]["kind"] == "ai"
    assert card["extension"]["severity"] == "moderate"
    assert card["suggestions"][0]["label"] == "Order a viral load test"
    assert card["suggestions"][0]["isRecommended"] is True
    passages = card["extension"]["passages"]
    assert [p["chunk_id"] for p in passages] == ["sahcs_adult_art_2024__sahcs_adult_art_2024__p32_c1"]
    assert passages[0]["text"]
    assert passages[0]["page_number"] == 32
    assert passages[0]["source_path"]


@pytest.mark.parametrize(
    "severity, indicator",
    [("critical", "critical"), ("high", "critical"), ("moderate", "warning"), ("low", "info"), (None, "warning"), ("odd", "warning")],
)
def test_indicator_follows_severity(severity, indicator):
    from backend.cards import indicator_for

    assert indicator_for(severity) == indicator


def test_long_title_is_cut_to_140(api):
    from backend.cards import card_from_saved

    alert = {"alert_id": "a", "title": "x" * 300, "message": "m", "evidence": {}, "source": "rule", "severity": None}
    card = card_from_saved(alert, {"retrieved": [], "explanation": {"text": "", "used_llm": False}})
    assert len(card.summary) == 140
    assert card.summary.endswith("…")


def test_visit_check_without_ai_calls_no_model(api):
    body = _check(api, use_ai=False).json()
    assert api.model.calls == []
    assert body["ai_review"] == "not_run"
    assert body["model"] is None
    assert [c["uuid"] for c in body["cards"]] == ["tdf_creatinine_overdue"]


def test_failed_model_is_never_green(api):
    api.model = FakeModel({}, fail=True)
    body = _check(api, patient_id="P003", note="Feels well.").json()
    assert body["ai_review"] == "failed"
    assert body["status"] != "GREEN"


def test_no_model_server_set_is_503_and_no_record(api):
    api.model = None
    r = _check(api)
    assert r.status_code == 503
    assert r.json() == {"detail": "No AI model server is set up."}
    with Session(api.engine) as s:
        from backend.records import VisitCheck

        assert s.exec(select(VisitCheck)).all() == []


def test_visit_check_with_the_plan(api):
    body = _check(api, include_plan=True).json()
    assert body["plan"] is not None
    assert body["plan"]["error"] is None
    assert body["plan"]["management_plan"]
    assert "plan" in api.model.calls


def test_visit_check_is_saved_once_as_written(api):
    from backend.records import VisitCheck

    body = _check(api, note="Mild headache since Monday.").json()
    with Session(api.engine) as s:
        rows = s.exec(select(VisitCheck)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.visit_id == body["visit_id"]
    assert row.patient_id == "P001"
    assert row.note == "Mild headache since Monday."
    assert row.status == body["status"]
    assert row.model == "fake-model"
    assert row.app_version == "test"
    assert row.origin == "api"
    assert [a["alert_id"] for a in row.alerts] == [c["uuid"] for c in body["cards"]]
    assert len(row.results) == len(row.alerts)


def test_a_failed_save_still_returns_the_results(api):
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(api.engine)  # the database is there but has no tables
    r = _check(api)
    assert r.status_code == 200
    assert r.json()["record_saved"] is False
    assert r.json()["cards"]


@pytest.mark.parametrize(
    "body",
    [
        {"note": "x" * 20001},
        {"note": "ok", "agentic": True},
        {},
        {"note": "ok", "use_ai": "sometimes"},
    ],
)
def test_bad_visit_check_requests_are_422(api, body):
    r = api.client.post("/api/patients/P001/visits", json=body, headers=LOCAL)
    assert r.status_code == 422
    assert api.model.calls == []


def test_an_unexpected_failure_stays_generic(api):
    def broken():
        raise RuntimeError("index file C:/secret/path is corrupt")

    api.services.search = broken
    client = api.client.__class__(api.app, base_url="http://localhost", raise_server_exceptions=False)
    r = client.post("/api/patients/P001/visits", json={"note": "x"}, headers=LOCAL)
    assert r.status_code == 500
    assert "secret" not in r.text


# Decisions


def test_acknowledge_one_alert(api):
    visit = _check(api).json()
    r = _decide(api, visit["visit_id"], {"alert_id": "tdf_creatinine_overdue", "action": "Acknowledge"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visit_id"] == visit["visit_id"]
    assert body["decisions"][0]["alert_id"] == "tdf_creatinine_overdue"
    assert body["decisions"][0]["action"] == "Acknowledge"
    assert body["all_resolved"] is False
    assert body["unresolved"] == [c["uuid"] for c in visit["cards"] if c["uuid"] != "tdf_creatinine_overdue"]


def test_resolve_every_alert(api):
    visit = _check(api).json()
    ids = [c["uuid"] for c in visit["cards"]]
    decisions = [{"alert_id": ids[0], "action": "Override", "reason": "Already addressed"}]
    decisions += [{"alert_id": i, "action": "Acknowledge"} for i in ids[1:]]
    body = _decide(api, visit["visit_id"], *decisions).json()
    assert body["all_resolved"] is True
    assert body["unresolved"] == []
    assert {d["alert_id"]: d["action"] for d in body["decisions"]} == {d["alert_id"]: d["action"] for d in decisions}


def test_override_other_needs_a_comment(api):
    visit_id = _check(api).json()["visit_id"]
    r = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Other"})
    assert r.status_code == 422
    r = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Other", "comment": "  "})
    assert r.status_code == 422
    r = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Other", "comment": "Seen at the renal clinic"})
    assert r.status_code == 200
    assert r.json()["decisions"][0]["comment"] == "Seen at the renal clinic"


@pytest.mark.parametrize(
    "decision",
    [
        {"alert_id": "tdf_creatinine_overdue", "action": "Override"},
        {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Because I said so"},
        {"alert_id": "tdf_creatinine_overdue", "action": "Unreviewed"},
        {"alert_id": "tdf_creatinine_overdue", "action": "Acknowledge", "comment": "x" * 2001},
        {"alert_id": "not_in_this_visit", "action": "Acknowledge"},
    ],
)
def test_bad_decisions_are_422_and_save_nothing(api, decision):
    from backend.records import AlertDecision

    visit_id = _check(api).json()["visit_id"]
    good = {"alert_id": "P001_001", "action": "Acknowledge"}
    r = _decide(api, visit_id, good, decision)
    assert r.status_code == 422
    with Session(api.engine) as s:
        assert s.exec(select(AlertDecision)).all() == []  # all or nothing


def test_empty_decision_list_is_422(api):
    visit_id = _check(api).json()["visit_id"]
    assert _decide(api, visit_id).status_code == 422


def test_reason_and_comment_dropped_on_acknowledge(api):
    visit_id = _check(api).json()["visit_id"]
    body = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Acknowledge", "reason": "Not applicable", "comment": "hm"}).json()
    assert body["decisions"][0]["reason"] == ""
    assert body["decisions"][0]["comment"] == ""


def test_a_changed_mind_keeps_both_and_the_latest_counts(api):
    from backend.records import AlertDecision

    visit_id = _check(api).json()["visit_id"]
    _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Acknowledge"})
    body = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Patient declined"}).json()
    latest = next(d for d in body["decisions"] if d["alert_id"] == "tdf_creatinine_overdue")
    assert latest["action"] == "Override"
    assert latest["reason"] == "Patient declined"
    with Session(api.engine) as s:
        rows = s.exec(select(AlertDecision).order_by(AlertDecision.id)).all()
    assert [(r.action, r.reason) for r in rows] == [("Acknowledge", ""), ("Override", "Patient declined")]
    assert rows[1].title == "Creatinine monitoring overdue while on TDF"
    assert rows[1].source == "rule"

