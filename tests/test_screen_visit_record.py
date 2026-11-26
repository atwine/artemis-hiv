"""Fix 9 on the real screen: Finalize saves the decisions, and a patient's last results can be reopened.

Drives app.py headlessly. Records go to a temporary folder, never to Data/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from artemis.rules.checks import Alert
from modules.explanation_generator import ExplanationResult
from tests import pipeline_harness as h

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ARTEMIS_CUSTOM_PATIENTS_PATH", str(tmp_path / "custom_patients.json"))
    folder = tmp_path / "records"
    monkeypatch.setenv("ARTEMIS_VISIT_RECORDS_DIR", str(folder))
    return folder


def _app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    return at


def _select(at: AppTest, patient_id: str) -> None:
    box = next(s for s in at.selectbox if s.label == "Select patient")
    box.select(next(o for o in box.options if o.split(" - ")[0] == patient_id)).run()


def _finalize(at: AppTest):
    return next(b for b in at.button if b.label == "Finalize / Close visit")


def _lines(folder: Path) -> list:
    return [json.loads(line) for f in sorted(folder.glob("*.jsonl")) for line in f.read_text(encoding="utf-8").splitlines()]


def test_finalize_saves_each_decision_and_other_needs_a_comment(records: Path) -> None:
    at = _app()
    _select(at, "P001")
    alerts = [
        Alert("tdf_creatinine_overdue", "Creatinine monitoring overdue while on TDF", "m", {}, ""),
        Alert("P001_001", "Missing Viral Load Monitoring", "m", {"type": "llm_screening", "severity": "moderate"}, "", source="ai"),
    ]
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = "P001"
    at.session_state["analysis_visit_id"] = "visit-1"
    at.session_state["analysis_status"] = "AMBER"
    at.session_state["analysis_screening_outcome"] = "ok"
    at.session_state["analysis_alerts"] = alerts
    at.session_state["analysis_results"] = [
        {"alert": a, "retrieved": [], "explanation": ExplanationResult(text="x", used_chunks=[], used_llm=False)} for a in alerts
    ]
    at.run()
    at.radio(key="alert_action_tdf_creatinine_overdue").set_value("Acknowledge").run()
    at.radio(key="alert_action_P001_001").set_value("Override").run()
    at.selectbox(key="alert_override_reason_P001_001").set_value("Other (say why)").run()
    assert _finalize(at).disabled
    assert any("comment" in i.value for i in at.info)

    at.text_area(key="alert_override_comment_P001_001").input("Viral load done at another clinic.").run()
    assert not _finalize(at).disabled
    _finalize(at).click().run()
    assert any(s.value.startswith("Visit finalized and saved") for s in at.success)

    saved = _lines(records)[-1]
    assert (saved["event"], saved["visit_id"], saved["patient_id"]) == ("finalized", "visit-1", "P001")
    assert [(d["alert_id"], d["source"], d["action"], d["reason"], d["comment"]) for d in saved["decisions"]] == [
        ("tdf_creatinine_overdue", "rule", "Acknowledge", "", ""),
        ("P001_001", "ai", "Override", "Other (say why)", "Viral load done at another clinic."),
    ]


def test_a_patients_last_results_come_back_only_when_asked(records: Path) -> None:
    p = next(x for x in h.patients() if x["patient_id"] == "P001")
    shown = h.run_patient(p, records_dir=records)

    at = _app()
    _select(at, "P001")
    assert not [e for e in at.expander if e.label.startswith("Alert (")]
    button = next(b for b in at.button if b.label.startswith("Show last saved results"))
    button.click().run()

    titles = [e.label for e in at.expander if e.label.startswith("Alert (")]
    assert titles == [f"Alert ({'AI review' if a['source'] == 'ai' else 'Rule check'}): {a['title']}" for a in shown["alerts"]]
    assert any(c.value.startswith("Saved results from") for c in at.caption)
    # The note on screen is the one the results were made from, so no "note changed" warning.
    assert not any("note has changed" in w.value for w in at.warning)


def test_a_saved_visit_that_cannot_be_rebuilt_says_so_instead_of_crashing(records: Path) -> None:
    from artemis import visit_record as vr

    # A line in an older or damaged shape: an alert field this code doesn't know.
    vr.append_entry(records, {"event": "checks_run", "visit_id": "old", "patient_id": "P001", "saved_at": "2026-11-01T09:00:00+00:00",
                              "alerts": [{"alert_id": "A1", "headline": "old field name"}], "results": []})
    at = _app()
    _select(at, "P001")
    next(b for b in at.button if b.label.startswith("Show last saved results")).click().run()
    assert not at.exception
    assert any("could not be reopened" in w.value for w in at.warning)
    assert not [e for e in at.expander if e.label.startswith("Alert (")]
