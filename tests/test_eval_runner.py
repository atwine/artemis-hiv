"""Phase 2: the runner saves what scoring needs, guards the budget, and resumes without repeating work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from artemis.evaluation.cases import load_cases
from tests import pipeline_harness as h

ROOT = Path(__file__).resolve().parents[1]
ALERT = {"alert_id": "A1", "title": "Creatinine overdue on TDF", "message": "Last creatinine 478 days ago.",
         "issue_type": "monitoring_gap", "severity": "moderate", "recommended_action": "Repeat creatinine.", "citations": []}


class _Stub:
    """A model that answers like a server: a reply, then usage with a cost."""

    model = "stub-model"
    last_error = None
    last_note = None
    last_finish_reason = "stop"

    def __init__(self) -> None:
        self.last_usage: Dict[str, Any] = {}

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.last_usage = {"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001}
        return json.dumps([ALERT]) if isinstance(format, dict) else "{}"


def _case(case_id: str):
    return next(c for c in load_cases(ROOT / "eval" / "cases") if c.case_id == case_id)


def _rag():
    from modules.rag_engine import RagEngine

    return RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))


def test_a_run_record_holds_what_the_scoring_needs() -> None:
    from artemis.evaluation.runner import run_case
    from artemis.evaluation.scoring import score_run

    case = _case("P001")
    rec = run_case(case, _Stub(), _rag(), label="stub", repeat=1)
    assert (rec["case_id"], rec["model"], rec["model_id"], rec["repeat"]) == ("P001", "stub", "stub-model", 1)
    assert rec["screening"]["parse_status"] == "parsed_nonempty"
    assert len(rec["calls"]) >= 2 and rec["cost_usd"] == pytest.approx(0.001 * len(rec["calls"]))
    assert "Creatinine overdue on TDF" in [a["title"] for a in rec["alerts"]]
    assert score_run(case, rec["alerts"]).caught == {"creatinine_overdue"}
    json.dumps(rec)  # everything in it can be saved


def test_cost_comes_from_the_server_or_else_from_the_price() -> None:
    from artemis.evaluation.runner import cost_of

    assert cost_of([{"cost": 0.002}, {"cost": 0.003}], 1e-6, 1e-6) == pytest.approx(0.005)
    assert cost_of([{"prompt_tokens": 1000, "completion_tokens": 100}], 2e-6, 10e-6) == pytest.approx(0.003)
    assert cost_of([None], 2e-6, 10e-6) == 0.0  # a call that failed before the server answered


def test_the_budget_guard_refuses_a_run_that_could_pass_the_cap() -> None:
    from artemis.evaluation.runner import BudgetExceeded, check_budget

    check_budget(spent=1.0, checks=10, per_check=0.02, cap=5.0)  # 1.20 of 5.00: fine
    with pytest.raises(BudgetExceeded, match="5.00"):
        check_budget(spent=4.9, checks=10, per_check=0.02, cap=5.0)


def test_runs_already_saved_are_skipped(tmp_path: Path) -> None:
    from artemis.evaluation.runner import pending_runs, run_file_name

    cases = [_case("P001"), _case("P002")]
    (tmp_path / run_file_name("P001", 1)).write_text("{}", encoding="utf-8")
    todo: List[tuple] = [(c.case_id, k) for c, k in pending_runs(tmp_path, cases, repeats=2)]
    assert todo == [("P001", 2), ("P002", 1), ("P002", 2)]
