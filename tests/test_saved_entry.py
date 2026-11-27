"""A visit check as the backend saves it and reads it back (moved from the Streamlit visit-record
file into backend/records.py, plan 4C.6). The same entry gives the reply for a fresh check and a
reopened one, so a visit reads the same either way."""

from __future__ import annotations

import copy
import json

import pytest

from artemis.visit import AnalysisOptions, run_visit_analysis
from backend import records
from tests.api_fakes import FakeModel, fake_search, read_patients, replies_for


def _patient(pid: str) -> dict:
    return copy.deepcopy(next(p for p in read_patients() if p["patient_id"] == pid))


def _entry(result, note="Routine follow-up."):
    return records.json_safe(records.checks_entry(result, note=note, visit_date="2026-01-22", model="m",
                                                  app_version="test", visit_id="v1", saved_at=records.now()))


def _run(pid="P005", model=None):
    return run_visit_analysis(patient=_patient(pid), today_note="Routine follow-up.", rag=fake_search(),
                              llm_client=model or FakeModel(replies_for(pid)), options=AnalysisOptions())


def test_saved_alerts_come_back_exactly_as_they_were_found():
    result = _run()
    back = records.saved_alerts(_entry(result))
    assert [s.alert for s in back] == result.alerts
    assert [[c.chunk_id for c in s.retrieved] for s in back] == [[c.chunk_id for c in r["retrieved"]] for r in result.results]
    assert [s.explanation for s in back] == [r["explanation"].text for r in result.results]
    assert [s.severity for s in back] == [(a.evidence or {}).get("severity") for a in result.alerts]


def test_the_entry_holds_the_check_and_no_plan():
    """Only "Compare plans" makes a plan (owner, 2026-11-27), so a check's entry never holds one."""
    result = _run("P001")
    e = _entry(result)
    assert (e["event"], e["patient_id"], e["visit_id"], e["model"], e["app_version"]) == ("checks_run", "P001", "v1", "m", "test")
    assert (e["status"], e["ai_review"]) == (result.status, result.screening_outcome)
    assert (e["agentic_enabled"], e["plan"]) == (False, None)
    json.dumps(e)


def test_results_that_dont_line_up_with_the_alerts_are_an_error():
    e = _entry(_run())
    e["results"] = e["results"][:-1]
    with pytest.raises(ValueError):
        records.saved_alerts(e)


def test_a_saved_alert_with_no_title_is_an_error():
    e = _entry(_run())
    e["alerts"][0]["title"] = None
    with pytest.raises(ValueError, match="title"):
        records.saved_alerts(e)


def test_a_saved_visit_keeps_no_model_error_text():
    """The model connection's error text stays in the log, never in a saved visit (G26): it can
    carry part of the model server's address."""
    from artemis.ai.client import ChatReply

    class Down:
        model = "down"

        def chat(self, messages, format=None, options_override=None):  # noqa: A002
            return ChatReply(None, error="Model server call failed: port=8000 url: /v1/chat/completions")

    e = _entry(_run("P001", Down()))
    assert e["ai_review"] == "failed"
    assert "8000" not in json.dumps(e)
