"""What the clinician sees of the management plan: only what the AI actually said.

Owner's picks for fix 7:
- an item with no verdict from the AI shows "Not assessed", never "Matches your plan"
- when the clinician wrote no plan, every item shows "No plan to compare", whatever the AI said
- a regimen decision that isn't Switch, Hold or Continue gets a grey "Needs review" badge with
  the AI's own words, never a green "Continue"
- a plan that failed the app's own checks is shown with a warning that says so
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any, List, Optional

from artemis.plan.plan_json import parse_plan, regimen_decision_kind

_VERDICT_LABELS = {
    "Agree": "Matches your plan",
    "Disagree": "Differs from your plan",
    "Gap": "Not in your plan",
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
    for p in obj.get("problems") or []:
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


_TONES = {
    "red": ("#FDECEA", "#DC3545"),
    "amber": ("#FFF9E6", "#856404"),
    "green": ("#F0F8F0", "#1B5E20"),
    "grey": ("#EEEEEE", "#444444"),
}


def plan_html(view: PlanView) -> str:
    """The plan as HTML for the screen. All text from the AI is escaped."""
    e = lambda s: html.escape(str(s or ""))  # noqa: E731
    bg, fg = _TONES[view.regimen_tone]
    badge = (
        f"<span style='background:{bg};color:{fg};padding:4px 8px;border:1px solid {fg};"
        f"border-radius:12px;font-weight:600;'>{e(view.regimen_label)}</span>"
    )
    parts: List[str] = []
    if view.issues:
        parts.append(
            "<div style='background:#FFF4E5;color:#7A4B00;padding:10px;border-left:4px solid #FFA000;"
            "border-radius:8px;margin-bottom:12px;'><strong>This plan failed the app's own checks.</strong> "
            f"Treat it with care. Problems found: {e(', '.join(view.issues))}</div>"
        )
    said = f" <em>The AI wrote: {e(view.regimen_text)}</em>" if view.regimen_tone == "grey" and view.regimen_text else ""
    parts.append(
        "<div style='background:#FFFFFF;padding:14px;border-left:4px solid #2E86AB;margin-bottom:12px;border-radius:8px;'>"
        f"<div style='margin-bottom:6px;'>{badge} <strong style='margin-left:8px;'>ART regimen decision</strong>{said}</div>"
        f"<div style='color:#333;'>Reason: {e(view.regimen_reason)}</div></div>"
    )
    if view.items:
        rows = "".join(
            "<li style='margin-bottom:8px;'>"
            f"<div><strong>{e(i.problem)}</strong>: {e(i.action)}</div>"
            f"<div style='color:#444;font-size:12px;margin-top:2px;'><em>{e(i.verdict_label)}</em>"
            + (f": {e(i.explanation)}" if i.explanation and i.verdict_label not in {"No plan to compare", "Not assessed"} else "")
            + "</div>"
            f"<div style='color:#555;font-size:12px;margin-top:2px;'>Reason: {e(i.reason)}</div></li>"
            for i in view.items
        )
        parts.append(
            "<div style='background-color:#F0F8F0;padding:14px;border-left:4px solid #52B788;border-radius:8px;margin-bottom:12px;'>"
            "<h4 style='color:#1B5E20;margin:0 0 8px 0;'>Suggested Management Plan</h4>"
            f"<ol style='margin:0;padding-left:18px;'>{rows}</ol></div>"
        )
    for title, values, colour in (("Monitoring", view.monitoring, "#2E86AB"), ("Counselling", view.counselling, "#7B68AB")):
        if values:
            lis = "".join(f"<li>{e(v)}</li>" for v in values)
            parts.append(
                f"<div style='padding:14px;border-left:4px solid {colour};border-radius:8px;margin-bottom:12px;'>"
                f"<h4 style='color:{colour};margin:0 0 8px 0;'>{title}</h4><ul style='margin:0;padding-left:18px;'>{lis}</ul></div>"
            )
    return "\n".join(parts)
