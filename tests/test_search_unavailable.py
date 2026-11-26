"""G33 (owner's decision, 2026-11-26): when the guideline search model does not load, the AI review
is switched off for the visit and the screen says why; the fixed rule checks still run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from artemis.visit import AnalysisOptions, compute_overall_status, run_visit_analysis
from modules.rag_engine import RagEngine
from tests import pipeline_harness as h
from artemis.screen_text import status_banners

ROOT = Path(__file__).resolve().parents[1]


class _BrokenSearchModel(h.FakeEmbedder):
    loaded = False


class _CountingModel:
    model = "stub"
    last_error = None
    last_note = None
    last_finish_reason = "stop"

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.calls += 1
        return "[]"


def _run(embedder, model):
    rag = RagEngine(
        project_root=ROOT,
        guideline_paths=[],
        embedder=embedder,
        vector_store=h.FakeStore(json.loads((h.GOLDEN_DIR / "corpus.json").read_text(encoding="utf-8"))),
    )
    p = next(p for p in h.patients() if p["patient_id"] == "P001")
    messages = []
    result = run_visit_analysis(
        patient=p, today_note=p["today_encounter"]["note"], rag=rag, llm_client=model,
        options=AnalysisOptions(use_llm=True, agentic=False), on_status=lambda label, state: messages.append(label),
    )
    return result, messages


def test_a_search_model_that_did_not_load_switches_the_ai_review_off() -> None:
    model = _CountingModel()
    result, messages = _run(_BrokenSearchModel(), model)
    assert model.calls == 0
    assert result.screening_outcome == "search_unavailable"
    assert result.alerts and all(a.source == "rule" for a in result.alerts)  # rule alerts only
    assert all(r["retrieved"] == [] for r in result.results)  # no references from a broken search
    assert any("search model did not load" in m for m in messages)


def test_the_rule_checks_still_run_when_the_search_model_did_not_load() -> None:
    working, _ = _run(h.FakeEmbedder(), _CountingModel())
    broken, _ = _run(_BrokenSearchModel(), _CountingModel())
    rules = lambda r: [a.alert_id for a in r.alerts if a.source == "rule"]  # noqa: E731
    assert rules(broken) == rules(working)


def test_nothing_found_with_the_search_down_is_not_an_all_clear() -> None:
    assert compute_overall_status([], "search_unavailable") == "INCOMPLETE"
    texts = " ".join(text for _, text in status_banners("INCOMPLETE", "search_unavailable", 0))
    assert "Guideline search is unavailable" in texts and "AI review is off" in texts


def test_the_embedder_reports_a_model_that_did_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    import modules.embedder as embedder_module

    def boom(*args, **kwargs):
        raise OSError("no such model")

    monkeypatch.setattr(embedder_module, "SentenceTransformer", boom)
    assert embedder_module.Embedder(embedder_module.EmbedderConfig(model_name="all-MiniLM-L6v2")).loaded is False


def test_with_the_search_down_the_plan_step_does_not_run_either() -> None:
    rag = RagEngine(project_root=ROOT, guideline_paths=[], embedder=_BrokenSearchModel(),
                    vector_store=h.FakeStore(json.loads((h.GOLDEN_DIR / "corpus.json").read_text(encoding="utf-8"))))
    p = next(p for p in h.patients() if p["patient_id"] == "P001")
    model = _CountingModel()
    result = run_visit_analysis(patient=p, today_note=p["today_encounter"]["note"], rag=rag, llm_client=model,
                                options=AnalysisOptions(use_llm=True, agentic=True))
    assert model.calls == 0 and result.agentic_result is None


def test_with_the_ai_switched_off_a_broken_search_is_still_reported() -> None:
    rag = RagEngine(project_root=ROOT, guideline_paths=[], embedder=_BrokenSearchModel(),
                    vector_store=h.FakeStore(json.loads((h.GOLDEN_DIR / "corpus.json").read_text(encoding="utf-8"))))
    p = next(p for p in h.patients() if p["patient_id"] == "P001")
    result = run_visit_analysis(patient=p, today_note=p["today_encounter"]["note"], rag=rag, llm_client=None,
                                options=AnalysisOptions(use_llm=False, agentic=False))
    assert result.screening_outcome == "search_unavailable"

