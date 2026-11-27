"""Fix 7: the management plan shows only what the AI actually said."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import List

from artemis.ai.client import ChatReply

ROOT = Path(__file__).resolve().parents[1]


def _baseline_plan(pid: str) -> str:
    d = json.loads((ROOT / "eval" / "baseline" / f"{pid}__run1.json").read_text(encoding="utf-8"))
    return d["agentic_result"]["updated_management_plan_text"]


# What the clinician sees, from real plans saved in the baseline.

def test_no_verdict_with_no_clinician_plan_says_no_plan_to_compare() -> None:
    from artemis.plan.view import read_plan

    view = read_plan(_baseline_plan("P005"), clinician_plan_written=False)  # P005 wrote no plan
    assert [i.verdict_label for i in view.items] == ["No plan to compare", "No plan to compare"]


def test_no_verdict_with_a_clinician_plan_says_not_assessed_never_agree() -> None:
    from artemis.plan.view import read_plan

    plan = json.loads(_baseline_plan("P001"))
    del plan["problems"][1]["clinician_plan_for_this_problem"]  # the model gave no verdict here
    view = read_plan(json.dumps(plan), clinician_plan_written=True)
    labels = [i.verdict_label for i in view.items]
    assert labels[0] == "Matches your plan"  # the model really said Agree
    assert labels[1] == "Not assessed"


def test_an_uncertain_regimen_decision_is_grey_needs_review_with_the_models_words() -> None:
    from artemis.plan.view import read_plan

    view = read_plan(_baseline_plan("P004"), clinician_plan_written=True)
    assert view.regimen_label == "Needs review"
    assert view.regimen_tone == "grey"
    assert view.regimen_text.startswith("Uncertain: cannot determine")


def test_a_continue_decision_stays_green() -> None:
    from artemis.plan.view import read_plan

    view = read_plan(_baseline_plan("P001"), clinician_plan_written=True)
    assert (view.regimen_label, view.regimen_tone) == ("Continue", "green")


def test_a_plan_that_failed_its_checks_keeps_its_issues() -> None:
    """The issues go with the plan (the reply adds the warning: tests/test_compare_plans.py)."""
    from artemis.plan.view import read_plan

    issues = ["problem_0_missing_key:clinician_plan_for_this_problem"]
    view = read_plan(_baseline_plan("P005"), clinician_plan_written=False, issues=issues)
    assert view.issues == issues
    assert view.items and {i.verdict_label for i in view.items} == {"No plan to compare"}


# The AI step that writes the plan.

class PlanModel:
    """Stand-in model: answers every plan request with the same reply and records the calls."""

    model = "stub"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: List[dict] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.calls.append({"messages": messages, "format": format, "options": options_override})
        return ChatReply(self.reply)


def _run_flow(pid: str, reply: str):
    from artemis.patient.record import build_patient_context
    from artemis.patient.summary import build_stage1_summary
    from artemis.plan.flow import QueryContext, run_agentic_flow
    from tests import pipeline_harness as h

    p = copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == pid))
    summary = build_stage1_summary(patient=p, context=build_patient_context(p))
    model = PlanModel(reply)
    result = run_agentic_flow(
        QueryContext(question_text="q", patient_raw=p, patient_summary=summary),
        embedder=h.FakeEmbedder(),
        vector_store=h.FakeStore([]),
        llm_client=model,
    )
    return result, model


def test_the_plan_step_asks_for_a_verdict_on_every_item_and_reads_the_summary() -> None:
    _, model = _run_flow("P002", _baseline_plan("P001"))
    system = model.calls[0]["messages"][0]["content"]
    user = model.calls[0]["messages"][1]["content"]
    assert "ONLY include if" not in system
    assert "clinician_plan_for_this_problem" in system and "every problem" in system
    assert '"not_recorded"' in user  # the fix 6 summary reaches the plan step
    assert "Jane Roe" not in user  # no patient names to the model


def test_there_is_no_separate_verification_call() -> None:
    _, model = _run_flow("P001", _baseline_plan("P001"))
    assert all(c["format"] == "json" for c in model.calls)


def test_a_plan_that_never_passes_its_checks_comes_back_marked() -> None:
    result, _ = _run_flow("P005", _baseline_plan("P005"))  # no verdicts: fails every time
    assert result.updated_management_plan_text
    assert any("clinician_plan_for_this_problem" in i for i in result.plan_issues)


def test_a_plan_whose_parts_have_the_wrong_type_is_read_without_crashing() -> None:
    """Code review, 2026-11-27: "problems": 5 raised TypeError after the model had been paid."""
    from artemis.plan.view import read_plan

    for odd in ('{"problems": 5}', '{"problems": true}', '{"problems": "none", "art_regimen_decision": "Continue"}',
                '{"problems": [1, "x", null], "monitoring_plan": 3, "patient_counselling": null}'):
        view = read_plan(odd, clinician_plan_written=True)
        assert view is not None and view.items == [], odd
