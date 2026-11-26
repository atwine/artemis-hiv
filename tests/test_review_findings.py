"""Phase 1 close (1.Z): faults found by the code and spec reviews, each pinned by a test."""

from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path
from typing import Any, Dict, List

from streamlit.testing.v1 import AppTest

from artemis.ai.client import ChatReply
from tests import pipeline_harness as h

ROOT = Path(__file__).resolve().parents[1]


def _patient(pid: str) -> Dict[str, Any]:
    return copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == pid))


def test_a_negated_creatinine_in_pasted_text_is_not_a_result() -> None:
    from artemis.patient.record import build_patient_context
    from artemis.rules.checks import run_alerts

    p = _patient("P002")
    p["labs"] = {"labs_narrative": [{"date": p["today_encounter"]["date"], "narrative_text": "No creatinine done this year.", "source": "pasted"}]}
    ids = [a.alert_id for a in run_alerts(build_patient_context(p))]
    assert "tdf_creatinine_pasted_only" not in ids
    assert "tdf_creatinine_missing" in ids


def test_the_agentic_demo_calls_the_plan_step_with_arguments_it_accepts() -> None:
    from artemis.plan.flow import run_agentic_flow

    tree = ast.parse((ROOT / "agentic_demo.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "run_agentic_flow"]
    assert calls
    for call in calls:
        inspect.signature(run_agentic_flow).bind(*[None] * len(call.args), **{k.arg: None for k in call.keywords})


def test_a_gap_verdict_reads_as_partly_in_the_plan() -> None:
    from artemis.plan.view import read_plan

    plan = {
        "problems": [
            {"problem": "Renal", "action": "Repeat creatinine", "reason": "On TDF",
             "clinician_plan_for_this_problem": {"decision": "Gap"}},
            {"problem": "VL", "action": "Viral load", "reason": "Due",
             "clinician_plan_for_this_problem": {"decision": "Not Addressed"}},
        ],
        "art_regimen_decision": {"decision": "Continue", "reason": "Stable"},
    }
    view = read_plan(json.dumps(plan), clinician_plan_written=True)
    assert [i.verdict_label for i in view.items] == ["Partly in your plan", "Not in your plan"]


class _CutPlanModel:
    model = "stub"

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        if isinstance(format, dict):  # the screening call
            return ChatReply("[]", finish_reason="stop")
        # every plan reply hits the length limit
        return ChatReply('{"problems": [{"problem": "Renal", "action": "Repeat creat', finish_reason="length")


def test_a_cut_off_plan_is_reported_as_cut_off() -> None:
    from artemis.visit import AnalysisOptions, run_visit_analysis
    from modules.rag_engine import RagEngine

    rag = RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))
    result = run_visit_analysis(
        patient=_patient("P002"), today_note="", rag=rag, llm_client=_CutPlanModel(), options=AnalysisOptions(agentic=True)
    )
    assert "cut_off" in result.agentic_result.plan_issues


class _ClashModel:
    model = "stub"

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        alert = {"alert_id": "tdf_creatinine_overdue", "title": "AI creatinine", "message": "m", "issue_type": "monitoring_gap",
                 "severity": "moderate", "recommended_action": "a", "citations": []}
        return ChatReply(json.dumps([alert]) if isinstance(format, dict) else "{}", finish_reason="stop")


def test_ai_and_rule_alerts_never_share_an_id() -> None:
    from artemis.visit import AnalysisOptions, run_visit_analysis
    from modules.rag_engine import RagEngine

    rag = RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))
    result = run_visit_analysis(patient=_patient("P001"), today_note="", rag=rag, llm_client=_ClashModel(), options=AnalysisOptions())
    ids: List[str] = [a.alert_id for a in result.alerts]
    assert "tdf_creatinine_overdue" in ids and len(ids) == len(set(ids)) == 2


def test_a_plan_that_could_not_be_made_says_so(tmp_path: Path, monkeypatch) -> None:
    from artemis.plan.flow import AgenticResult

    monkeypatch.setenv("ARTEMIS_CUSTOM_PATIENTS_PATH", str(tmp_path / "custom_patients.json"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.session_state["analysis_ran"] = True
    at.session_state["analysis_patient_id"] = next(s for s in at.selectbox if s.label == "Select patient").value.split(" - ")[0]
    at.session_state["analysis_status"] = "GREEN"
    at.session_state["analysis_screening_outcome"] = "ok"
    at.session_state["agentic_debug_enabled"] = True
    at.session_state["agentic_debug_result"] = AgenticResult(updated_management_plan_text=None, plan_issues=["no_reply"])
    at.run()
    assert any("management plan could not be produced" in w.value for w in at.warning)
