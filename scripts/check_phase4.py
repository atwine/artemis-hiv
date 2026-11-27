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

Since B1/B2 (owner, 2026-11-27) the visit check makes no plan; each run's plan is made after it
through "Compare plans". Added to the keep rule then, before that run: a run whose saved plan
passed its checks gets the same plan text, as a plan made; one whose saved plan failed them is
never shown as a clean plan (it fails, or comes with its issues).

Since 4C.5 (owner, 2026-11-27: "A, through the backend") each run goes through the evaluation's
own path, backend/evaluation.py run_case: the case's patient into a throwaway database as the app
stores it, then the check and the plan through the routes. The keep rule is unchanged.

Since the two fixed rules were reworded to name the guideline's action (owner, 2026-11-27: "A,
accept the wording"), the saved run is compared with the accepted new text of those fixed-rule
alerts and the passages that text finds (eval/phase4/accepted-rule-wording.json); everything the
AI said is still compared with the saved run as it is.
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
ACCEPTED = ROOT / "eval" / "phase4" / "accepted-rule-wording.json"
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


def with_accepted_rule_wording(record: Dict[str, Any], accepted: Dict[str, Any]) -> Dict[str, Any]:
    """The saved run as now expected: the accepted text and passages for reworded fixed-rule alerts.

    Only alerts the saved run marks as fixed-rule ("rule") may be changed; the record itself is
    left as saved."""
    rules = {a["alert_id"] for a in record["alerts"] if a.get("source") == "rule"}
    passages = (accepted.get("passages") or {}).get(record["case_id"], {})
    in_this_run = {a["alert_id"] for a in record["alerts"]}
    for alert_id in (set(accepted.get("messages") or {}) & in_this_run) | set(passages):
        if alert_id not in rules:
            raise ValueError(f"{record['case_id']} {alert_id} is not a fixed-rule alert; its wording can't be accepted")
    messages = accepted.get("messages") or {}
    alerts = [{**a, "message": messages[a["alert_id"]]} if a["alert_id"] in messages else dict(a)
              for a in record["alerts"]]
    return {**record, "alerts": alerts, "retrieved": {**record["retrieved"], **passages}}


def _same(a: Dict[str, Any]) -> tuple:
    return (a["alert_id"], a["title"], a["message"], a.get("source"), (a.get("evidence") or {}).get("severity"))


def _summary(cases: Dict[str, Any], runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    from artemis.evaluation.scoring import score_run, summarize

    s = summarize([score_run(cases[r["case_id"]], r["alerts"]) for r in runs])
    return {k: v for k, v in vars(s).items()}


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from artemis import config
    from artemis.evaluation.cases import load_cases
    from artemis.plan.view import read_plan
    from backend.evaluation import RunFailed, run_case

    from artemis.guidelines.vector_store import ChromaVectorStore

    rag = config.guideline_search()
    if not rag.search_ready or not isinstance(rag._vector_store, ChromaVectorStore):
        print("The search model or the kept Chroma index did not start; nothing checked.")
        return 1
    rag.ensure_indexed()
    cases = {c.case_id: c for c in load_cases(ROOT / "eval" / "cases")}
    as_saved = [json.loads(Path(f).read_text(encoding="utf-8")) for f in sorted(glob.glob(str(RUNS / "*.json")))]
    accepted = json.loads(ACCEPTED.read_text(encoding="utf-8"))
    saved = [with_accepted_rule_wording(r, accepted) for r in as_saved]

    replayed, problems = [], []
    plans_made = plans_failed = plans_flagged = 0
    for record in saved:
        run = f"{record['case_id']} run {record['repeat']}"
        try:  # the evaluation's own path (plan 4C.5): the patient through the database, then the routes
            now = run_case(cases[record["case_id"]], SavedReplies(record), rag, label="phase4-check",
                           repeat=record["repeat"])
        except RunFailed as exc:
            problems.append(f"{run}: {exc}")
            continue
        replayed.append(now)
        # The plan step's own checks; the app's "flag:" marks (an Uncertain plan, 2026-11-27) are
        # counted apart, since the saved runs were made before them.
        step_issues = [i for i in now["plan_issues"] if not i.startswith("flag:")]
        plans_flagged += len(step_issues) != len(now["plan_issues"])
        if [_same(a) for a in now["alerts"]] != [_same(a) for a in record["alerts"]]:
            problems.append(f"{run}: alerts differ")
        shown = [b["chunk_id"] for b in (now["screening"] or {}).get("screening_bundle") or []]
        if shown != [b["chunk_id"] for b in (record["screening"] or {}).get("screening_bundle") or []]:
            problems.append(f"{run}: the AI was shown different passages")
        if now["retrieved"] != record["retrieved"]:
            problems.append(f"{run}: an alert's passages differ")
        if now["status"] != record["status"].replace("YELLOW", "AMBER"):
            problems.append(f"{run}: status {now['status']} vs saved {record['status']}")
        if record.get("plan_issues"):
            plans_failed += 1
            readable = now["plan_text"] is not None and read_plan(now["plan_text"], clinician_plan_written=True)
            if readable and not step_issues:
                problems.append(f"{run}: a plan that failed its checks came back clean")
        else:
            plans_made += 1
            if now["plan_text"] != record["plan_text"] or step_issues:
                problems.append(f"{run}: the plan differs from the saved one")

    before = _summary(cases, saved)
    after = _summary(cases, replayed) if len(replayed) == len(saved) else None
    met = not problems and after == before
    lines = [
        "Phase 4 check: GLM's final 2B run (glm-5.2-t0-5q) replayed through the evaluation's backend path (4C.5).",
        f"Runs: {len(saved)} saved, {len(replayed)} replayed (real kept index, saved replies, nothing spent).",
        f"Scores as saved (2B):  {json.dumps(_summary(cases, as_saved), sort_keys=True)}",
        f"Scores expected (2B with the accepted rule wording, {ACCEPTED.name}): {json.dumps(before, sort_keys=True)}",
        f"Scores through the API: {json.dumps(after, sort_keys=True)}",
        f"Runs with differences: {len(problems)}",
        "Also compared per run: the passages the AI was shown, and each alert's passages (kept Chroma index).",
        f"Plans through Compare plans: {plans_made} the same as saved, {plans_failed} saved as failing their checks, none shown clean"
        " (any that differ count as runs with differences).",
        f"Plans the app now flags (an Uncertain verdict or no row assessed; shown with their warning): {plans_flagged}",
        f"Keep rule (same alerts and passages in every run, identical scores): {'MET' if met else 'NOT MET'}",
        *problems[:30],
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:10]))
    return 0 if met else 2


if __name__ == "__main__":
    raise SystemExit(main())
