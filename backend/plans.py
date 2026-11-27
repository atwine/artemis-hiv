"""The AI management plan of a saved visit ("Compare plans", plan B1/B2): what is saved of the
plan step's result, and how a saved plan goes to the screen.

The plan step (artemis/visit.py management_plan) gives the AI's plan text and the checks it
failed, or {"error", "type"} when it stopped. The saved row keeps the text as it came back; the
screen shape is read from it each time, by artemis/plan/view.py, as the cards are from a check.
"""

from __future__ import annotations

import datetime
from typing import Any, List, Optional

from artemis.plan.view import PlanView, read_plan
from artemis.screen_text import PLAN_FAILED, PLAN_ISSUES_NOTE
from backend.models import ManagementPlan, PlanItem, PlanRegimen
from backend.records import VisitPlan, iso


def plan_row(result: Any, *, visit_id: str, model: Optional[str], made_at: datetime.datetime) -> VisitPlan:
    """The row to save for one run of the plan step."""
    if isinstance(result, dict):  # the step stopped; only the kind of failure is kept
        text, issues, error_type = None, [], str(result.get("type") or "error")
    else:
        text = getattr(result, "updated_management_plan_text", None)
        issues, error_type = [str(i) for i in getattr(result, "plan_issues", None) or []], None
    view = read_plan(text, clinician_plan_written=True) if isinstance(text, str) else None
    return VisitPlan(visit_id=visit_id, made_at=made_at, model=model, outcome="made" if view is not None else "failed",
                     plan_text=text, issues=issues + (unsure_flags(view) if view is not None else []), error_type=error_type)


def unsure_flags(view: PlanView) -> List[str]:
    """What makes a readable plan one not to keep (owner, 2026-11-27: "Yes, flag it"): a regimen
    verdict of "Uncertain", or no problem row with a verdict the app recognises. Marked "flag:" to
    tell them from the plan step's own checks. A flagged plan is shown with its warning, and
    pressing "Compare plans" again asks the AI again."""
    flags = []
    if view.regimen_label == "Needs review":  # the AI's decision was Uncertain, or not one of the four
        flags.append("flag:regimen_uncertain")
    if view.items and all(i.verdict_label == "Not assessed" for i in view.items):
        flags.append("flag:no_row_assessed")
    return flags


def is_good(row: VisitPlan) -> bool:
    """A plan worth keeping: readable and passing the app's own checks. Pressing "Compare plans"
    again shows it with nothing run; any other plan is tried again (owner: "A, keep a good plan")."""
    return row.outcome == "made" and not row.issues


def plan_reply(row: VisitPlan, *, note: str, saved: bool = True) -> ManagementPlan:
    """A saved plan in screen shape. Each item is compared with the note the visit was checked on:
    with no note, every item says there is no plan to compare."""
    view = read_plan(row.plan_text, clinician_plan_written=bool(note.strip())) if row.outcome == "made" else None
    common = dict(visit_id=row.visit_id, made_at=iso(row.made_at), model=row.model, issues=list(row.issues),
                  saved=saved)
    if view is None:
        return ManagementPlan(**common, outcome="failed", regimen=None, items=[], monitoring=[], counselling=[],
                              issues_note=None, error=PLAN_FAILED)
    return ManagementPlan(
        **common, outcome="made",
        regimen=PlanRegimen(label=view.regimen_label, tone=view.regimen_tone, text=view.regimen_text,
                            reason=view.regimen_reason),
        items=[PlanItem(problem=i.problem, action=i.action, reason=i.reason, verdict_label=i.verdict_label,
                        explanation=i.explanation) for i in view.items],
        monitoring=view.monitoring, counselling=view.counselling,
        issues_note=PLAN_ISSUES_NOTE if row.issues else None, error=None,
    )
