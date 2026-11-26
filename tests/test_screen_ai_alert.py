"""Fix 8 on the real screen: a cut-off AI review, a missing severity and an unseen citation are all visible.

Drives app.py headlessly with an analysis result put in place the way _run_analysis leaves it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from artemis.rules.checks import Alert
from modules.explanation_generator import ExplanationResult
from artemis.guidelines.vector_store import VectorSearchResult

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def at(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("ARTEMIS_CUSTOM_PATIENTS_PATH", str(tmp_path / "custom_patients.json"))
    app_test = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    app_test.run()
    return app_test


def test_a_cut_off_review_with_an_odd_alert_shows_every_warning(at: AppTest) -> None:
    patient_id = next(s for s in at.selectbox if s.label == "Select patient").value.split(" - ")[0]
    alert = Alert(
        alert_id="A1",
        title="Creatinine rising on TDF",
        message="Creatinine 0.9 then 1.4 mg/dL.",
        evidence={
            "type": "llm_screening",
            "severity": "not given",
            "recommended_action": "Repeat creatinine.",
            "citations": [
                {"chunk_id": "c1", "page_number": 3, "shown_to_ai": True},
                {"chunk_id": "made_up", "page_number": 99, "shown_to_ai": False},
            ],
        },
        query_hint="",
        source="ai",
    )
    chunk = VectorSearchResult(chunk_id="c1", document="text", metadata={"page_number": 7}, distance=0.1)
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = patient_id
    at.session_state["analysis_status"] = "AMBER"
    at.session_state["analysis_screening_outcome"] = "cut_off"
    at.session_state["analysis_alerts"] = [alert]
    at.session_state["analysis_results"] = [
        {"alert": alert, "retrieved": [chunk], "explanation": ExplanationResult(text="x", used_chunks=[], used_llm=False)}
    ]
    at.run()

    warnings = [w.value for w in at.warning]
    assert any(w.startswith("AI review incomplete (its reply was cut off") for w in warnings)
    assert any(w.startswith("Severity not given") for w in warnings)
    shown = "\n".join(m.value for m in at.markdown)
    assert "References (the passages the AI was shown and cited)" in shown
    assert "1. Guidelines · p. 7" in shown
    assert "2. Guidelines · p. 99: not among the passages the AI was given" in shown
