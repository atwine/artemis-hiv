"""Fix 3: rule alerts are never dropped, and a failed AI review is never shown as clean.

These call the visit analysis directly with a stand-in model and search (no server needed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import pytest

from artemis.ai.client import ChatReply
from artemis.visit import AnalysisOptions, run_visit_analysis
from modules.rag_engine import RagEngine
from tests import pipeline_harness as h

ROOT = Path(__file__).resolve().parents[1]
AI_ALERT = {
    "alert_id": "P001_001",
    "title": "Missing Viral Load Monitoring",
    "message": "Viral load is due.",
    "issue_type": "monitoring_gap",
    "severity": "moderate",
    "recommended_action": "Order a viral load.",
    "citations": [],
}


class StubModel:
    model = "stub"

    def __init__(self, reply: Optional[str], error: Optional[str] = None) -> None:
        self._reply, self._error = reply, error

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        return ChatReply(self._reply, error=self._error)


def _patient(pid: str) -> dict:
    return next(p for p in h.patients() if p["patient_id"] == pid)


def _run(pid: str, model: StubModel):
    rag = RagEngine(
        project_root=ROOT,
        guideline_paths=[],
        embedder=h.FakeEmbedder(),
        vector_store=h.FakeStore(json.loads((h.GOLDEN_DIR / "corpus.json").read_text(encoding="utf-8"))),
    )
    p = _patient(pid)
    return run_visit_analysis(
        patient=p,
        today_note=p["today_encounter"]["note"],
        rag=rag,
        llm_client=model,
        options=AnalysisOptions(use_llm=True),
    )


def _titles(alerts: List) -> List[str]:
    return [a.title for a in alerts]


def test_rule_alerts_stay_next_to_the_ai_alerts() -> None:
    result = _run("P001", StubModel(json.dumps([AI_ALERT])))
    assert "Creatinine monitoring overdue while on TDF" in _titles(result.alerts)
    assert "Missing Viral Load Monitoring" in _titles(result.alerts)
    sources = {a.title: a.source for a in result.alerts}
    assert sources["Creatinine monitoring overdue while on TDF"] == "rule"
    assert sources["Missing Viral Load Monitoring"] == "ai"


def test_a_rule_alert_is_kept_when_the_ai_finds_nothing() -> None:
    result = _run("P001", StubModel("[]"))
    assert _titles(result.alerts) == ["Creatinine monitoring overdue while on TDF"]
    assert result.status != "GREEN"
    assert result.screening_outcome == "ok"


@pytest.mark.parametrize(
    "model, outcome",
    [
        (StubModel("Sorry, I could not produce a list."), "unreadable"),
        (StubModel(None, error="connection refused"), "failed"),
    ],
)
def test_a_failed_ai_review_is_never_green(model: StubModel, outcome: str) -> None:
    result = _run("P002", model)  # P002: no rule fires
    assert result.alerts == []
    assert result.screening_outcome == outcome
    assert result.status != "GREEN"


def test_the_ai_switched_off_is_reported_as_not_run() -> None:
    rag = RagEngine(project_root=ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))
    p = _patient("P002")
    result = run_visit_analysis(
        patient=p, today_note="", rag=rag, llm_client=None, options=AnalysisOptions(use_llm=False)
    )
    assert result.screening_outcome == "not_run"
