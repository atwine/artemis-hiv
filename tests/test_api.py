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
OVERRIDE_REASONS = [
    "Already done, not documented", "Test not available here", "Not right for this patient",
    "Patient declined", "Will address at next visit", "Other (say why)",
]


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
    # Stored as value_umol_per_l in the demo file; sent as value + unit (owner, 2026-11-26).
    assert body["labs"]["creatinine"] == [{"date": "2024-10-01", "value": "88", "unit": "umol/L", "source": "record"}]
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
    assert [c["extension"]["alert_id"] for c in body["cards"]] == [a.alert_id for a in direct.alerts]
    assert [c["uuid"] for c in body["cards"]] == [f'{body["visit_id"]}:{a.alert_id}' for a in direct.alerts]
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
    card = next(c for c in _check(api).json()["cards"] if c["extension"]["alert_id"] == "tdf_creatinine_overdue")
    assert card["summary"] == "Creatinine monitoring overdue while on TDF"
    assert card["detail"].startswith("Creatinine last recorded")
    assert card["indicator"] == "warning"  # no severity on a rule alert counts as moderate
    assert card["source"] == {"label": "ARTEMIS fixed rule", "topic": {"code": "rule", "display": "Fixed rule check", "system": "https://github.com/atwine/artemis-hiv/alert-source"}}
    assert card["extension"]["kind"] == "rule"
    assert card["extension"]["severity"] is None
    # A rule alert's passages come from a search for it.
    assert len(card["extension"]["passages"]) == 5


def test_ai_card_quotes_the_passages_it_cited(api):
    card = next(c for c in _check(api).json()["cards"] if c["extension"]["alert_id"] == "P001_001")
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

    from artemis.rules.checks import Alert

    alert = Alert(alert_id="a", title="x" * 300, message="m", evidence={}, query_hint="")
    card = card_from_saved(alert, [], "", severity=None, visit_id="v1")
    assert len(card.summary) == 140
    assert card.summary.endswith("…")


def test_visit_check_without_ai_calls_no_model(api):
    body = _check(api, use_ai=False).json()
    assert api.model.calls == []
    assert body["ai_review"] == "not_run"
    assert body["model"] is None
    assert [c["extension"]["alert_id"] for c in body["cards"]] == ["tdf_creatinine_overdue"]


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


def test_card_ids_differ_between_visits(api):
    """CDS Hooks wants each card's uuid to be its own; the same alert in two visits gets two."""
    first = _check(api).json()["cards"][0]["uuid"]
    second = _check(api).json()["cards"][0]["uuid"]
    assert first != second


def test_no_database_set_is_503_before_any_model_call(api):
    """Without a database the run couldn't be saved or decided on, so it isn't run (or paid for)."""
    api.services.engine = None
    r = _check(api)
    assert r.status_code == 503
    assert r.json() == {"detail": "The visit-record database is not set up."}
    assert api.model.calls == []


def test_alerts_and_results_out_of_step_are_an_error_not_lost_cards():
    from backend.cards import cards_from_entry

    entry = {"visit_id": "v1", "alerts": [{"alert_id": "a", "title": "t", "message": "m"}] * 2, "results": [{}]}
    with pytest.raises(ValueError):
        cards_from_entry(entry)


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
    assert [a["alert_id"] for a in row.alerts] == [c["extension"]["alert_id"] for c in body["cards"]]
    assert len(row.results) == len(row.alerts)


def test_a_failed_save_still_returns_the_results(api):
    from sqlmodel import SQLModel

    SQLModel.metadata.drop_all(api.engine)  # the database is there but has no tables
    r = _check(api)
    assert r.status_code == 200
    assert r.json()["record_saved"] is False
    assert r.json()["cards"]
    from artemis.screen_text import RECORD_NOT_SAVED

    assert ["warning", RECORD_NOT_SAVED] in [[b["level"], b["text"]] for b in r.json()["banners"]]


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
    ids = [c["extension"]["alert_id"] for c in visit["cards"]]
    assert body["unresolved"] == [i for i in ids if i != "tdf_creatinine_overdue"]


def test_resolve_every_alert(api):
    visit = _check(api).json()
    ids = [c["extension"]["alert_id"] for c in visit["cards"]]
    decisions = [{"alert_id": ids[0], "action": "Override", "reason": "Already done, not documented"}]
    decisions += [{"alert_id": i, "action": "Acknowledge"} for i in ids[1:]]
    body = _decide(api, visit["visit_id"], *decisions).json()
    assert body["all_resolved"] is True
    assert body["unresolved"] == []
    assert {d["alert_id"]: d["action"] for d in body["decisions"]} == {d["alert_id"]: d["action"] for d in decisions}


def test_override_other_needs_a_comment(api):
    visit_id = _check(api).json()["visit_id"]
    r = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Other (say why)"})
    assert r.status_code == 422
    r = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Other (say why)", "comment": "  "})
    assert r.status_code == 422
    r = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Other (say why)", "comment": "Seen at the renal clinic"})
    assert r.status_code == 200
    assert r.json()["decisions"][0]["comment"] == "Seen at the renal clinic"


@pytest.mark.parametrize(
    "decision",
    [
        {"alert_id": "tdf_creatinine_overdue", "action": "Override"},
        {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Because I said so"},
        {"alert_id": "tdf_creatinine_overdue", "action": "Override", "reason": "Already addressed"},  # an older reason
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
    body = _decide(api, visit_id, {"alert_id": "tdf_creatinine_overdue", "action": "Acknowledge", "reason": "Not right for this patient", "comment": "hm"}).json()
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



# Plan item 4.7: the API follows docs/screen-checklist.md and sends artemis/screen_text.py's wording.


def test_result_and_status_types_come_from_the_one_list():
    from typing import get_args

    from artemis.visit import AI_REVIEW_OUTCOMES, STATUSES
    from backend.models import AiReview, Status

    assert get_args(AiReview) == AI_REVIEW_OUTCOMES
    assert get_args(Status) == STATUSES


@pytest.mark.parametrize("status", ["GREEN", "AMBER", "RED", "INCOMPLETE"])
@pytest.mark.parametrize("outcome", ["not_run", "ok", "failed", "unreadable", "cut_off", "partly_read", "search_unavailable"])
def test_every_result_and_status_can_be_sent(status, outcome):
    from artemis.visit import AI_REVIEW_OUTCOMES, STATUSES
    from backend.models import VisitCheckResponse

    assert outcome in AI_REVIEW_OUTCOMES and status in STATUSES
    VisitCheckResponse(
        visit_id="v", patient_id="P", visit_date="2026-01-22", saved_at="2026-01-22T08:00:00+00:00",
        status=status, ai_review=outcome, model=None, cards=[], plan=None, record_saved=True,
        banners=[], disclaimer="d", finalize_note=None,
    )


def test_banners_and_disclaimer_are_the_screens_own_words(api):
    from artemis.screen_text import DISCLAIMER, FINALIZE_BLOCKED, status_banners

    body = _check(api).json()
    expected = status_banners(body["status"], body["ai_review"], len(body["cards"]))
    assert [(b["level"], b["text"]) for b in body["banners"]] == expected
    assert body["disclaimer"] == DISCLAIMER
    assert body["finalize_note"] == FINALIZE_BLOCKED  # alerts are waiting for a decision


def test_card_heading_and_references_are_the_screens_own_words(api):
    from artemis.screen_text import alert_heading, alert_references, citation_line

    visit = _check(api).json()
    from backend.records import VisitCheck

    with Session(api.engine) as s:
        from artemis.visit_record import restore
        from backend.records import entry_from_check

        restored = restore(entry_from_check(s.get(VisitCheck, visit["visit_id"])))
    for card, result in zip(visit["cards"], restored["analysis_results"]):
        alert = result["alert"]
        heading, lines = alert_references(alert, result["retrieved"])
        assert card["extension"]["heading"] == alert_heading(alert)
        assert card["extension"]["references_heading"] == heading
        assert card["extension"]["references"] == lines
        for p in card["extension"]["passages"]:
            expected = citation_line(p["source_path"], p["page_number"]) if p["page_number"] is not None else None
            assert p["citation"] == expected


def test_ai_card_reference_names_the_guideline_and_printed_page(api):
    card = next(c for c in _check(api).json()["cards"] if c["extension"]["alert_id"] == "P001_001")
    assert card["extension"]["heading"] == "Alert (AI review): Missing Viral Load Monitoring"
    assert card["extension"]["references"]
    assert all(" · p. " in line for line in card["extension"]["references"])


def test_search_model_not_loaded_turns_the_ai_off_and_says_so(api):
    """docs/screen-checklist.md, search_unavailable: red banner, AI review and plan off, rule
    alerts with no guideline references."""
    from artemis.visit import SEARCH_UNAVAILABLE
    from tests.api_fakes import fake_search

    broken = fake_search(ready=False)
    api.services.search = lambda: broken
    r = _check(api, include_plan=True)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai_review"] == "search_unavailable"
    assert body["banners"][0]["level"] == "error"
    assert SEARCH_UNAVAILABLE in body["banners"][0]["text"]
    assert api.model.calls == []
    assert body["cards"] and all(c["extension"]["kind"] == "rule" for c in body["cards"])
    assert all(c["extension"]["passages"] == [] and c["extension"]["references"] == [] for c in body["cards"])
    # The plan step didn't run, so there's no plan and no "could not be produced" message; the
    # red banner says why, as on the Streamlit screen.
    assert body["plan"] is None


def test_a_plan_step_that_ran_and_failed_says_so():
    from backend.cards import plan_from_entry

    failed = plan_from_entry({"agentic_enabled": True, "plan": {"error": "boom", "type": "RuntimeError"}})
    assert failed.error == "The management plan could not be produced."
    assert "boom" not in failed.model_dump_json()
    assert plan_from_entry({"agentic_enabled": True, "plan": None}) is None  # did not run
    assert plan_from_entry({"agentic_enabled": False, "plan": None}) is None  # not asked for


def test_finalize_note_clears_once_every_alert_is_decided(api):
    from artemis.screen_text import FINALIZE_BLOCKED

    visit = _check(api).json()
    ids = [c["extension"]["alert_id"] for c in visit["cards"]]
    first = _decide(api, visit["visit_id"], {"alert_id": ids[0], "action": "Acknowledge"}).json()
    assert first["finalize_note"] == (FINALIZE_BLOCKED if len(ids) > 1 else None)
    rest = _decide(api, visit["visit_id"], *[{"alert_id": i, "action": "Acknowledge"} for i in ids]).json()
    assert rest["finalize_note"] is None


def test_no_alerts_means_nothing_to_finalize(api):
    api.services.patients = lambda: [{**next(p for p in read_patients() if p["patient_id"] == "P001"), "labs": {"creatinine": [{"date": "2026-01-01", "value_umol_per_l": 80}]}}]
    body = _check(api, use_ai=False).json()
    if body["cards"]:
        pytest.skip("this patient still raises a rule alert")
    assert body["finalize_note"] is None


def test_a_decision_saved_with_an_older_reason_still_reads(api):
    """Saved decisions keep the reason they were saved with (owner, 2026-11-26); only new ones are checked."""
    from backend import records

    visit_id = _check(api).json()["visit_id"]
    old = [{"alert_id": "tdf_creatinine_overdue", "source": "rule", "title": "T", "severity": None,
            "action": "Override", "reason": "Already addressed", "comment": ""}]
    with Session(api.engine) as s:
        records.add_decisions(s, visit_id, old, saved_at="2026-11-20T08:00:00+00:00")
    body = _decide(api, visit_id, {"alert_id": "P001_001", "action": "Acknowledge"}).json()
    assert {d["alert_id"]: d["reason"] for d in body["decisions"]}["tdf_creatinine_overdue"] == "Already addressed"


def test_every_lab_result_the_api_returns_has_its_unit(api):
    """Owner, 2026-11-26 ("A, as recorded"): each result in the unit it was recorded in, with the
    value, unit and date as separate fields, so the website never guesses a unit. No conversion."""
    seen = 0
    for p in api.client.get("/api/patients", headers=LOCAL).json():
        body = api.client.get(f"/api/patients/{p['patient_id']}", headers=LOCAL).json()
        assert "labs_narrative" not in body["labs"]
        for test, results in body["labs"].items():
            for r in results:
                assert set(r) == {"date", "value", "unit", "source"}, (p["patient_id"], test, r)
                assert r["unit"] and r["value"] and r["date"], (p["patient_id"], test, r)
                seen += 1
    assert seen >= 8  # P001 to P004 have structured results


def test_lab_results_keep_the_unit_they_were_recorded_in(api):
    record = {**next(p for p in read_patients() if p["patient_id"] == "P001"),
              "labs": {"creatinine": [{"date": "2026-01-01", "value": "1.1", "unit": "mg/dL", "source": "today"}]}}
    api.services.patients = lambda: [record]
    body = api.client.get("/api/patients/P001", headers=LOCAL).json()
    assert body["labs"]["creatinine"] == [{"date": "2026-01-01", "value": "1.1", "unit": "mg/dL", "source": "today"}]


def test_lab_notes_typed_as_text_come_back_as_text(api):
    body = api.client.get("/api/patients/P005", headers=LOCAL).json()
    assert body["labs"] == {}
    assert body["lab_notes"] and all(set(n) == {"date", "source", "text"} and n["text"] for n in body["lab_notes"])


def test_card_explanations_are_plain_text_only(api):
    """No raw patient dicts, passage dumps or internal ids in what the website shows (owner, 2026-11-26)."""
    for card in _check(api).json()["cards"]:
        text = card["extension"]["explanation"]
        assert text, card["uuid"]
        for raw in ("Patient evidence", "Guideline excerpts", "chunk_id", "raw_issue", "{", "page="):
            assert raw not in text, (card["uuid"], raw, text)
    ai = next(c for c in _check(api).json()["cards"] if c["extension"]["alert_id"] == "P001_001")
    assert ai["extension"]["explanation"] == ai["detail"]


def test_cards_carry_the_values_box_and_the_key_sentence(api):
    """Owner, 2026-11-26: both by code, no AI change."""
    visit = _check(api).json()
    rule = next(c for c in visit["cards"] if c["extension"]["alert_id"] == "tdf_creatinine_overdue")
    assert rule["extension"]["values"] == [{"label": "creatinine", "value": "88", "unit": "umol/L", "date": "2024-10-01"}]
    ai = next(c for c in visit["cards"] if c["extension"]["alert_id"] == "P001_001")
    assert ai["extension"]["values"] == [{"label": "viral load", "value": "40", "unit": "copies/mL", "date": "2025-10-01"}]
    for card in visit["cards"]:
        for v in card["extension"]["values"]:
            assert v["label"] and v["value"] and v["unit"] and v["date"]
        sentence = card["extension"]["key_sentence"]
        if sentence is not None:
            assert any(sentence in p["text"] for p in card["extension"]["passages"]), card["uuid"]
    reopened = api.client.get(f"/api/visits/{visit['visit_id']}", headers=LOCAL).json()
    assert [c["extension"]["values"] for c in reopened["cards"]] == [c["extension"]["values"] for c in visit["cards"]]
    assert [c["extension"]["key_sentence"] for c in reopened["cards"]] == [c["extension"]["key_sentence"] for c in visit["cards"]]


def test_a_plan_with_problems_comes_back_with_its_issue_codes(api):
    """The plan step reports problems as short codes ("invalid_json", "cut_off"); found by the Phase 4
    replay: the API's Plan type expected objects, so such a visit check failed with a 500."""
    api.model = FakeModel({**replies_for("P001"), "plan": "not json at all"})
    r = _check(api, include_plan=True)
    assert r.status_code == 200, r.text
    plan = r.json()["plan"]
    assert plan["issues"] and all(isinstance(i, str) for i in plan["issues"])
