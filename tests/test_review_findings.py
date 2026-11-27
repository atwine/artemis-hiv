"""Phase 1 close (1.Z): faults found by the code and spec reviews, each pinned by a test."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

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
    from artemis.visit import management_plan
    from modules.rag_engine import RagEngine

    rag = RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))
    plan = management_plan(patient=_patient("P002"), today_note="", rag=rag, llm_client=_CutPlanModel())
    assert "cut_off" in plan.plan_issues


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
