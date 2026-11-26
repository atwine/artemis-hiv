"""The Phase 4 check: does the evaluation through the backend match Phase 2B's numbers?

    python scripts/check_phase4.py

Replays GLM's final 2B run (eval/phase2/runs/glm-5.2-t0-5q: 11 cases x 3) through the backend's
own visit-check route, with the real kept guideline index and a stand-in model that gives back
each run's saved replies (its search questions, its screening reply and how it ended, its plan).
Nothing is sent to any model and nothing is spent (owner's pick, 2026-11-26).

Keep rule, written before the run: every run gives the same alerts as saved, and the scores are
identical. Tightened after review (2026-11-26), since fixed replies alone would pass with a broken
index: every run must also give the AI the same passages, and each alert the same passages, as the
saved run, and the search must be the kept Chroma index. Writes eval/phase4/api-replay-check.txt.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RUNS = ROOT / "eval" / "phase2" / "runs" / "glm-5.2-t0-5q"
OUT = ROOT / "eval" / "phase4" / "api-replay-check.txt"
SCREENING = "You are ARTEMIS, an HIV medication safety screening system"


class SavedReplies:
    """A stand-in model that answers each kind of call with one saved run's reply."""

    model = "glm-5.2 (saved replies)"

    def __init__(self, record: Dict[str, Any]) -> None:
        from artemis.ai.search_questions import _INSTRUCTIONS

        self._record, self._questions_prompt = record, _INSTRUCTIONS

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        from artemis.ai.client import ChatReply

        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        screening = self._record["screening"] or {}
        if system.startswith(SCREENING):
            return ChatReply(screening.get("raw_output"), finish_reason=screening.get("finish_reason"))
        if system == self._questions_prompt:
            return ChatReply(json.dumps(screening.get("search_questions") or []), finish_reason="stop")
        return ChatReply(self._record.get("plan_text") or "", finish_reason="stop")


def _same(a: Dict[str, Any]) -> tuple:
    return (a["alert_id"], a["title"], a["message"], a.get("source"), (a.get("evidence") or {}).get("severity"))


def _summary(cases: Dict[str, Any], runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    from artemis.evaluation.scoring import score_run, summarize

    s = summarize([score_run(cases[r["case_id"]], r["alerts"]) for r in runs])
    return {k: v for k, v in vars(s).items()}


def main() -> int:
    from dotenv import load_dotenv
    from fastapi.testclient import TestClient
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel, create_engine

    load_dotenv(ROOT / ".env")
    import app
    from artemis.evaluation.cases import load_cases
    from backend import records
    from backend.main import create_app
    from backend.services import Services
    from backend.settings import Settings

    from artemis.guidelines.vector_store import ChromaVectorStore

    rag = app._get_rag_engine(prefer_chroma=True, embedding_model_name=app.EMBEDDING_MODEL, engine_version=5)
    if not rag.search_ready or not isinstance(rag._vector_store, ChromaVectorStore):
        print("The search model or the kept Chroma index did not start; nothing checked.")
        return 1
    rag.ensure_indexed()
    cases = {c.case_id: c for c in load_cases(ROOT / "eval" / "cases")}
    saved = [json.loads(Path(f).read_text(encoding="utf-8")) for f in sorted(glob.glob(str(RUNS / "*.json")))]

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    box: Dict[str, Any] = {}
    services = Services(patients=lambda: [c.patient for c in cases.values()], search=lambda: rag,
                        model_client=lambda: box["model"], engine=engine, app_version="phase4-check")
    client = TestClient(create_app(settings=Settings(visit_checks_per_minute=10_000), services=services),
                        base_url="http://localhost")

    replayed, problems = [], []
    for record in saved:
        case = cases[record["case_id"]]
        box["model"] = SavedReplies(record)
        note = (case.patient.get("today_encounter") or {}).get("note") or ""
        r = client.post(f"/api/patients/{case.case_id}/visits", json={"note": note, "include_plan": True},
                        headers={"Origin": "http://localhost:3000"})
        if r.status_code != 200:
            problems.append(f"{record['case_id']} run {record['repeat']}: HTTP {r.status_code} {r.text[:200]}")
            continue
        with Session(engine) as s:
            row = records.get_check(s, r.json()["visit_id"])
            alerts, results, debug = list(row.alerts), list(row.results), dict(row.screening_debug or {})
        replayed.append({"case_id": record["case_id"], "repeat": record["repeat"], "alerts": alerts})
        if [_same(a) for a in alerts] != [_same(a) for a in record["alerts"]]:
            problems.append(f"{record['case_id']} run {record['repeat']}: alerts differ")
        shown = [b["chunk_id"] for b in debug.get("screening_bundle") or []]
        if shown != [b["chunk_id"] for b in (record["screening"] or {}).get("screening_bundle") or []]:
            problems.append(f"{record['case_id']} run {record['repeat']}: the AI was shown different passages")
        found = {a["alert_id"]: [c["chunk_id"] for c in res.get("retrieved") or []] for a, res in zip(alerts, results)}
        if found != record["retrieved"]:
            problems.append(f"{record['case_id']} run {record['repeat']}: an alert's passages differ")
        if r.json()["status"] != record["status"].replace("YELLOW", "AMBER"):
            problems.append(f"{record['case_id']} run {record['repeat']}: status {r.json()['status']} vs saved {record['status']}")

    before = _summary(cases, saved)
    after = _summary(cases, replayed) if len(replayed) == len(saved) else None
    met = not problems and after == before
    lines = [
        "Phase 4 check: GLM's final 2B run (glm-5.2-t0-5q) replayed through the backend's visit-check route.",
        f"Runs: {len(saved)} saved, {len(replayed)} replayed (real kept index, saved replies, nothing spent).",
        f"Scores as saved (2B):  {json.dumps(before, sort_keys=True)}",
        f"Scores through the API: {json.dumps(after, sort_keys=True)}",
        f"Runs with differences: {len(problems)}",
        "Also compared per run: the passages the AI was shown, and each alert's passages (kept Chroma index).",
        f"Keep rule (same alerts and passages in every run, identical scores): {'MET' if met else 'NOT MET'}",
        *problems[:30],
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:7]))
    return 0 if met else 2


if __name__ == "__main__":
    raise SystemExit(main())
