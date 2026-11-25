"""Fix 2: results on screen belong to the selected patient, and the add-case form resets.

These drive the real Streamlit screen (app.py) headlessly. No model call is made: the tests
put an analysis result in place the way _run_analysis leaves it, or use the add-case form.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from modules.alert_rules import Alert
from modules.explanation_generator import ExplanationResult

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    # Added cases go to a temporary file, never to Data/custom_patients.json.
    monkeypatch.setenv("ARTEMIS_CUSTOM_PATIENTS_PATH", str(tmp_path / "custom_patients.json"))
    app_test = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    app_test.run()
    return app_test


def _select(at: AppTest, patient_id: str) -> None:
    box = next(s for s in at.selectbox if s.label == "Select patient")
    box.select(next(o for o in box.options if o.split(" - ")[0] == patient_id)).run()


def _selected(at: AppTest) -> str:
    return next(s for s in at.selectbox if s.label == "Select patient").value


def _pretend_analysed(at: AppTest, patient_id: str) -> None:
    alert = Alert(
        alert_id="tdf_creatinine_overdue",
        title="Creatinine monitoring overdue while on TDF",
        message="Creatinine last recorded 400 days ago.",
        evidence={},
        query_hint="",
    )
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = patient_id
    at.session_state["analysis_status"] = "YELLOW"
    at.session_state["analysis_alerts"] = [alert]
    at.session_state["analysis_results"] = [
        {"alert": alert, "retrieved": [], "explanation": ExplanationResult(text="x", used_chunks=[], used_llm=False)}
    ]
    at.run()


def _alert_titles_on_screen(at: AppTest) -> list:
    return [e.label for e in at.expander if e.label.startswith("Alert:")]


def test_results_stay_with_the_patient_they_were_run_for(at: AppTest) -> None:
    _select(at, "P001")
    _pretend_analysed(at, "P001")
    assert _alert_titles_on_screen(at) == ["Alert: Creatinine monitoring overdue while on TDF"]

    _select(at, "P002")
    assert _alert_titles_on_screen(at) == []
    assert any("Save encounter" in i.value for i in at.info)
    assert not any(w.value.startswith("YELLOW") for w in at.warning)

    # Coming back doesn't bring the old results back (that waits for the saved record, fix 9b).
    _select(at, "P001")
    assert _alert_titles_on_screen(at) == []


def test_adding_a_case_clears_the_form_and_selects_the_new_case(at: AppTest) -> None:
    at.text_input(key="new_case_patient_id").input("T-900")
    at.text_input(key="new_case_art_regimen").input("TDF, 3TC, DTG")
    at.text_area(key="new_case_todays_lab_results").input("creatinine, 2026-01-10, 90")
    at.text_area(key="new_case_previous_lab_results").input("viral_load, 2025-06-01, 40")
    next(b for b in at.button if b.label == "Add case to patient list").click().run()

    assert not at.exception
    assert _selected(at).split(" - ")[0] == "T-900"
    assert at.text_area(key="new_case_todays_lab_results").value == ""
    assert at.text_area(key="new_case_previous_lab_results").value == ""
    assert at.text_input(key="new_case_patient_id").value == ""
