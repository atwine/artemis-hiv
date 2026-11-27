"""Stand-ins for the backend tests: a model that replays saved replies and a guideline search
over a fixed set of passages. No model server, no embedding model and no index are loaded.

The replies and passages are the ones tests/pipeline_harness.py uses (tests/golden), taken
from the A100 baseline, so the alerts are the real model's alerts for each patient.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


from artemis.ai.client import ChatReply
from artemis.ai.search_questions import _INSTRUCTIONS as _QUESTIONS_PROMPT
from artemis.guidelines.vector_store import VectorSearchResult, VectorStore
from modules.rag_engine import RagEngine

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
# The tests' own made-up patients: a copy of the app's seed patients (P001-P009, Kintu-Test 001),
# so tests never depend on the app's data (owner, 2026-11-27: the app's patients live only in the
# database).
FIXTURE_PATIENTS = ROOT / "tests" / "fixtures" / "patients.json"
CLINIC_DAY = ROOT / "tests" / "fixtures" / "clinic_day.json"  # the tests' copy of the demo day


def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 3}


class FakeEmbedder:
    loaded = True  # the search model loaded (RagEngine.search_ready); see fake_search(ready=False)

    def __init__(self, loaded: bool = True) -> None:
        self.loaded = loaded

    def encode(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] for _ in texts]


class FakeStore(VectorStore):
    """Ranks a fixed set of passages by how many words they share with the query."""

    def __init__(self, corpus: List[Dict[str, Any]]) -> None:
        self._corpus = corpus

    def index_guidelines(self, chunks, embedder) -> int:  # type: ignore[override]
        return 0

    def query(self, query_text, embedder, top_k=5):  # type: ignore[override]
        q = _words(query_text)
        scored = sorted(self._corpus, key=lambda c: (-len(q & _words(c["document"])), c["chunk_id"]))
        return [
            VectorSearchResult(chunk_id=c["chunk_id"], document=c["document"], metadata=dict(c["metadata"]), distance=0.5)
            for c in scored[:top_k]
        ]


def fake_search(*, ready: bool = True) -> RagEngine:
    """ready=False is a search model that did not load (G33): the AI review is switched off."""
    corpus = json.loads((GOLDEN / "corpus.json").read_text(encoding="utf-8"))
    return RagEngine(project_root=ROOT, guideline_paths=[], embedder=FakeEmbedder(loaded=ready), vector_store=FakeStore(corpus))


class FakeModel:
    """Answers each kind of call with the baseline's real reply for one patient.

    `fail=True` behaves like a model server that didn't answer: no text, and an error.
    """

    model = "fake-model"

    def __init__(self, replies: Dict[str, str], *, fail: bool = False) -> None:
        self._replies = replies
        self._fail = fail
        self.calls: List[str] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        if system.startswith("You are ARTEMIS, an HIV medication safety screening system"):
            kind = "screening"
        elif system == _QUESTIONS_PROMPT:  # the screening's search questions, not the plan
            kind = "questions"
        elif format is not None:
            kind = "plan"
        else:
            kind = "agentic_answer"
        self.calls.append(kind)
        if self._fail:
            return ChatReply("", error="connection refused (fake)")
        return ChatReply(self._replies.get(kind, ""), finish_reason="stop")


def replies_for(patient_id: str) -> Dict[str, str]:
    return json.loads((GOLDEN / "replies.json").read_text(encoding="utf-8")).get(patient_id, {})


def read_patients() -> List[Dict[str, Any]]:
    """The tests' made-up patients (tests/fixtures/patients.json), read, never written."""
    return json.loads(FIXTURE_PATIENTS.read_text(encoding="utf-8"))


def read_clinic_day() -> Dict[str, Any]:
    """The tests' copy of the demo day's schedule, read, never written."""
    return json.loads(CLINIC_DAY.read_text(encoding="utf-8"))


def memory_engine():
    """A throwaway SQLite database in memory with the app's tables, links checked as Postgres does:
    the evaluation's own (backend/evaluation.py), so tests and evaluation runs use the same one."""
    from backend.evaluation import memory_engine as engine

    return engine()
