"""What the clinician sees of the management plan: only what the AI actually said.

Owner's picks for fix 7:
- an item with no verdict from the AI shows "Not assessed", never "Matches your plan"
- when the clinician wrote no plan, every item shows "No plan to compare", whatever the AI said
- a regimen decision that isn't Switch, Hold or Continue gets a grey "Needs review" badge with
  the AI's own words, never a green "Continue"
- a plan that failed the app's own checks is shown with a warning that says so
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from artemis.plan.plan_json import parse_plan, regimen_decision_kind

_VERDICT_LABELS = {
    "Agree": "Matches your plan",
    "Disagree": "Differs from your plan",
    "Gap": "Partly in your plan",
    "Not Addressed": "Not in your plan",
}
_REGIMEN = {
    "Switch": ("Switch", "red"),
    "Hold temporarily": ("Hold temporarily", "amber"),
    "Continue": ("Continue", "green"),
    "Uncertain": ("Needs review", "grey"),
}


@dataclass(frozen=True)
class PlanItem:
    problem: str
    action: str
    reason: str
    verdict_label: str
    explanation: str = ""


@dataclass(frozen=True)
class PlanView:
    regimen_label: str
    regimen_tone: str
    regimen_text: str
    regimen_reason: str
    items: List[PlanItem]
    monitoring: List[str]
    counselling: List[str]
    issues: List[str] = field(default_factory=list)


def _texts(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, dict):
        out: List[str] = []
        for v in value.values():
            out += _texts(v if isinstance(v, list) else [v])
        return out
    return [str(value).strip()] if str(value or "").strip() else []


def read_plan(text: str, *, clinician_plan_written: bool, issues: Optional[List[str]] = None) -> Optional[PlanView]:
    obj = parse_plan(text)
    if obj is None:
        return None
    ard = obj.get("art_regimen_decision") or {}
    decision = str(ard.get("decision") or "").strip() if isinstance(ard, dict) else ""
    label, tone = _REGIMEN[regimen_decision_kind(decision)]
    items: List[PlanItem] = []
    problems = obj.get("problems")
    for p in problems if isinstance(problems, list) else []:  # the AI may send any type here
        if not isinstance(p, dict):
            continue
        cp = p.get("clinician_plan_for_this_problem")
        verdict = str(cp.get("decision") or "").strip() if isinstance(cp, dict) else ""
        if not clinician_plan_written:
            verdict_label = "No plan to compare"
        else:
            verdict_label = _VERDICT_LABELS.get(verdict, "Not assessed")
        items.append(
            PlanItem(
                problem=str(p.get("problem") or "").strip(),
                action=str(p.get("action") or "").strip(),
                reason=str(p.get("reason") or "").strip(),
                verdict_label=verdict_label,
                explanation=str(cp.get("explanation") or "").strip() if isinstance(cp, dict) else "",
            )
        )
    return PlanView(
        regimen_label=label,
        regimen_tone=tone,
        regimen_text=decision,
        regimen_reason=str(ard.get("reason") or "").strip() if isinstance(ard, dict) else "",
        items=items,
        monitoring=_texts(obj.get("monitoring_plan")),
        counselling=_texts(obj.get("patient_counselling")),
        issues=list(issues or []),
    )
