"""Stand-ins for the backend tests: a model that replays saved replies and a guideline search
over a fixed set of passages. No model server, no embedding model and no index are loaded.

The replies and passages are the ones tests/pipeline_harness.py uses (tests/golden), taken
from the A100 baseline, so the alerts are the real model's alerts for each patient.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

from artemis.guidelines.vector_store import VectorSearchResult, VectorStore
from modules.rag_engine import RagEngine

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"
MOCK_PATIENTS = ROOT / "Data" / "mock_patients.json"
CUSTOM_PATIENTS = ROOT / "Data" / "custom_patients.json"
DEMO_DAY_PATIENTS = ROOT / "Data" / "demo_day_patients.json"
CLINIC_DAY = ROOT / "Data" / "demo_clinic_day.json"


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

    `fail=True` behaves like a model server that didn't answer: no text, and last_error set.
    """

    model = "fake-model"

    def __init__(self, replies: Dict[str, str], *, fail: bool = False) -> None:
        self._replies = replies
        self._fail = fail
        self.last_error: Optional[str] = None
        self.last_finish_reason: Optional[str] = None
        self.calls: List[str] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        if system.startswith("You are ARTEMIS, an HIV medication safety screening system"):
            kind = "screening"
        elif format is not None:
            kind = "plan"
        else:
            kind = "agentic_answer"
        self.calls.append(kind)
        if self._fail:
            self.last_error = "connection refused (fake)"
            return ""
        self.last_finish_reason = "stop"
        return self._replies.get(kind, "")


def replies_for(patient_id: str) -> Dict[str, str]:
    return json.loads((GOLDEN / "replies.json").read_text(encoding="utf-8")).get(patient_id, {})


def read_patients() -> List[Dict[str, Any]]:
    """The demo patients, read (never written) from Data/."""
    out: List[Dict[str, Any]] = []
    for path in (MOCK_PATIENTS, CUSTOM_PATIENTS, DEMO_DAY_PATIENTS):
        if path.exists():
            out.extend(json.loads(path.read_text(encoding="utf-8")))
    return out


def read_clinic_day() -> Dict[str, Any]:
    """The demo day's schedule, read (never written) from Data/."""
    return json.loads(CLINIC_DAY.read_text(encoding="utf-8"))


def memory_engine():
    """A throwaway SQLite database in memory, with the tables made from the models."""
    import backend.records  # noqa: F401  (registers the tables)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine
