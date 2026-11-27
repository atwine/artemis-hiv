"""Run the app's whole visit, the check and then its plan, with no model server and no embeddings.

The model is a stand-in that replays the replies the real model gave in eval/baseline
(run 1 of each patient). The guideline search is a stand-in over the passages the baseline
retrieved, ranked by word overlap. Everything between them is the app's real code, run through
the backend itself (backend/evaluation.py run_visit: the patient into a throwaway database,
then "run checks" and "Compare plans" through the routes), so any change to how alerts are
built, combined, kept, labelled or shown changes the output here.

tests/test_pipeline_golden.py compares this output with tests/golden/pipeline.json.
Rebuild the stand-in data from eval/baseline with:  python tests/pipeline_harness.py fixtures
Rewrite the expected output on purpose with:         python tests/pipeline_harness.py golden
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))

from backend.evaluation import run_visit  # noqa: E402
from modules.rag_engine import RagEngine  # noqa: E402
from artemis.ai.client import ChatReply  # noqa: E402
from artemis.guidelines.vector_store import VectorSearchResult, VectorStore  # noqa: E402

def _words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 3}


class FakeEmbedder:
    loaded = True

    def encode(self, texts: List[str]) -> List[List[float]]:
        return [[0.0] for _ in texts]


class FakeStore(VectorStore):
    """Ranks a fixed set of passages by how many query words they share."""

    def __init__(self, corpus: List[Dict[str, Any]]) -> None:
        self._corpus = corpus

    def index_guidelines(self, chunks, embedder) -> int:  # type: ignore[override]
        return 0

    def query(self, query_text, embedder, top_k=5):  # type: ignore[override]
        q = _words(query_text)
        scored = []
        for c in self._corpus:
            score = len(q & _words(c["document"]))
            scored.append((-score, c["chunk_id"], c, score))
        scored.sort(key=lambda t: (t[0], t[1]))
        return [
            VectorSearchResult(
                chunk_id=c["chunk_id"], document=c["document"], metadata=dict(c["metadata"]),
                distance=round(1.0 / (1.0 + s), 6),
            )
            for _, _, c, s in scored[:top_k]
        ]


class ReplayClient:
    """Stand-in model: answers each kind of call with the baseline's real reply."""

    model = "replay"

    def __init__(self, replies: Dict[str, str]) -> None:
        self._replies = replies
        self.calls: List[Dict[str, str]] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        if system.startswith("You are ARTEMIS, an HIV medication safety screening system"):
            kind = "screening"
        elif format is not None:
            kind = "plan"
        else:
            kind = "agentic_answer"
        digest = hashlib.sha1(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.calls.append({"kind": kind, "messages_sha1": digest[:12]})
        return ChatReply(self._replies.get(kind, ""))


def _load(name: str) -> Any:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def patients() -> List[Dict[str, Any]]:
    """The patients the golden output covers: the tests' made-up patients with recorded replies."""
    replies = _load("replies.json")
    fixtures = json.loads((ROOT / "tests" / "fixtures" / "patients.json").read_text(encoding="utf-8"))
    return [p for p in fixtures if str(p["patient_id"]) in replies]


def _plain(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o)), ensure_ascii=False))


def run_patient(patient: Dict[str, Any]) -> Dict[str, Any]:
    """One patient's visit through the backend, with the stand-in model and search."""
    corpus = _load("corpus.json")
    client = ReplayClient(_load("replies.json")[str(patient["patient_id"])])
    rag = RagEngine(project_root=ROOT, guideline_paths=[], embedder=FakeEmbedder(), vector_store=FakeStore(corpus))
    note = (patient.get("today_encounter") or {}).get("note") or ""
    check, plan = run_visit(patient, note, client, rag)
    return _plain(
        {
            "status": check["status"],
            "alerts": [{k: v for k, v in a.items() if k != "severity"} for a in check["alerts"]],
            "results": [
                {
                    "alert_id": a["alert_id"],
                    "retrieved": [c["chunk_id"] for c in r.get("retrieved") or []],
                    "explanation": (r.get("explanation") or {}).get("text"),
                }
                for a, r in zip(check["alerts"], check["results"])
            ],
            "screening_parse_status": (check["screening_debug"] or {}).get("parse_status"),
            "screening_outcome": check["ai_review"],
            "plan_text": plan["plan_text"] if plan else None,
            "plan_issues": plan["issues"] if plan else [],
            "llm_calls": client.calls,
        }
    )


def run_all() -> Dict[str, Any]:
    return {str(p["patient_id"]): run_patient(p) for p in patients()}


def build_fixtures() -> None:
    """Take the stand-in data from eval/baseline (run 1 of each patient)."""
    corpus: Dict[str, Dict[str, Any]] = {}
    replies: Dict[str, Dict[str, str]] = {}
    for f in sorted((ROOT / "eval" / "baseline").glob("*__run1.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for res in d["results"]:
            for c in res["retrieved"]:
                corpus.setdefault(c["chunk_id"], {"chunk_id": c["chunk_id"], "document": c["excerpt"], "metadata": c["metadata"]})
        ag = d.get("agentic_result") or {}
        replies[str(d["patient_id"])] = {
            "screening": d["screening"]["raw_output"],
            "plan": ag.get("updated_management_plan_text") or "",
            "agentic_answer": ag.get("final_answer_text") or "",
        }
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    (GOLDEN_DIR / "corpus.json").write_text(json.dumps(sorted(corpus.values(), key=lambda c: c["chunk_id"]), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    (GOLDEN_DIR / "replies.json").write_text(json.dumps(replies, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"corpus: {len(corpus)} passages; replies for {len(replies)} patients")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "fixtures":
        build_fixtures()
    elif cmd == "golden":
        out = run_all()
        (GOLDEN_DIR / "pipeline.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"golden written for {len(out)} patients")
    else:
        print(__doc__)
