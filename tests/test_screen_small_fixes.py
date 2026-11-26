"""Fix 10 on the real screen, run headlessly: addresses, labels, regimen text, saved files."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from artemis.rules.checks import Alert
from modules.explanation_generator import ExplanationResult
from tests import pipeline_harness as h

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "custom_patients.json"
    monkeypatch.setenv("ARTEMIS_CUSTOM_PATIENTS_PATH", str(path))
    return path


def _app() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    return at


def _all_text(at: AppTest) -> str:
    parts = []
    for kind in (at.markdown, at.caption, at.info, at.warning, at.error, at.success):
        parts.extend(str(e.value) for e in kind)
    return "\n".join(parts)


def _select(at: AppTest, patient_id: str) -> None:
    box = next(s for s in at.selectbox if s.label == "Select patient")
    box.select(next(o for o in box.options if o.split(" - ")[0] == patient_id)).run()


def test_the_settings_panel_names_the_server_without_its_address(cases: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://10.0.0.1:8000/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    text = _all_text(_app())
    assert "10.0.0.1" not in text
    assert "address in .env" in text and "test-model" in text


def test_an_unreachable_ollama_is_reported(cases: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "")
    monkeypatch.setenv("OLLAMA_HOST", "127.0.0.1:9")
    assert any("isn't reachable" in w.value for w in _app().warning)


def test_regimen_text_is_shown_as_text_not_html(cases: Path) -> None:
    p = copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == "P001"))
    p["patient_id"] = "T-html"
    p["art_regimen_current"] = ["<b>TDF</b>"]
    cases.write_text(json.dumps([p]), encoding="utf-8")
    at = _app()
    _select(at, "T-html")
    regimen = [m.value for m in at.markdown if "Regimen:" in m.value]
    assert regimen and "&lt;b&gt;TDF&lt;/b&gt;" in regimen[0] and "<b>TDF</b>" not in regimen[0]


def test_labels_say_what_happened(cases: Path) -> None:
    at = _app()
    _select(at, "P001")
    assert "**Visit Type:** Not recorded" in [m.value for m in at.markdown]

    ai = Alert("A1", "Missing viral load", "No viral load in 6 months.", {"type": "llm_screening", "severity": "moderate"}, "", source="ai")
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = "P001"
    at.session_state["analysis_status"] = "AMBER"
    at.session_state["analysis_screening_outcome"] = "ok"
    at.session_state["analysis_alerts"] = [ai]
    at.session_state["analysis_results"] = [
        {"alert": ai, "retrieved": [], "explanation": ExplanationResult(text="x", used_chunks=[])}
    ]
    at.run()
    captions = [c.value for c in at.caption]
    assert not any("LLM unavailable" in c for c in captions)
    assert any("written by the AI review" in c for c in captions)


def test_a_no_alert_result_shows_the_summary_the_ai_read(cases: Path) -> None:
    at = _app()
    _select(at, "P001")
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = "P001"
    at.session_state["analysis_status"] = "GREEN"
    at.session_state["analysis_screening_outcome"] = "ok"
    at.session_state["analysis_patient_summary"] = {"current_regimen": ["TDF", "3TC", "DTG"], "not_recorded": []}
    at.run()
    text = _all_text(at)
    assert "What the AI was given about the patient" in text
    assert "meds_detected" not in text and "What patient facts were checked" not in text


def test_a_damaged_cases_file_is_never_overwritten(cases: Path) -> None:
    damaged = '[{"patient_id": "OLD-1"},]'
    cases.write_text(damaged, encoding="utf-8")
    at = _app()
    assert any("can't be read" in e.value for e in at.error)
    at.text_input(key="new_case_patient_id").input("T-901")
    at.multiselect(key="new_case_art_regimen").select("TLD")
    at.text_area(key="new_case_complaints").input("Cough.")
    next(b for b in at.button if b.label == "Add case to patient list").click().run()
    assert cases.read_text(encoding="utf-8") == damaged


def test_a_failed_ai_review_shows_no_raw_error_text(cases: Path) -> None:
    # Errors shown to users stay generic; the details go to the app log (code review, 1.Z).
    at = _app()
    _select(at, "P001")
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = "P001"
    at.session_state["analysis_status"] = "INCOMPLETE"
    at.session_state["analysis_screening_outcome"] = "failed"
    at.session_state["analysis_ollama_error"] = "Model server call failed: ReadTimeout: internal detail 42"
    at.run()
    text = _all_text(at)
    assert "AI review failed" in text
    assert "internal detail 42" not in text and "ReadTimeout" not in text
