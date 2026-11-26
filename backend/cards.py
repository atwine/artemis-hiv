"""Turn a saved visit check into what the screen gets: CDS Hooks cards and the plan.

Plain functions over the "checks_run" entry that artemis.visit_record.checks_entry builds (the
same dict that is saved), so a visit reads the same whether it just ran or was saved earlier.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from artemis.review import OVERRIDE_REASONS
from backend.models import Card, CardExtension, Coding, Passage, Plan, Source, Suggestion

SYSTEM = "https://github.com/atwine/artemis-hiv"

# The same ranking artemis.visit.compute_overall_status uses: no severity counts as moderate.
_INDICATOR = {"critical": "critical", "high": "critical", "moderate": "warning", "low": "info"}

_SOURCES = {
    "rule": Source(label="ARTEMIS fixed rule", topic=Coding(code="rule", display="Fixed rule check", system=f"{SYSTEM}/alert-source")),
    "ai": Source(label="ARTEMIS AI review", topic=Coding(code="ai", display="AI review against the guidelines", system=f"{SYSTEM}/alert-source")),
}

OVERRIDE_CODINGS = [
    Coding(code=re.sub(r"[^a-z]+", "-", r.lower()).strip("-"), display=r, system=f"{SYSTEM}/override-reason")
    for r in OVERRIDE_REASONS
]


def indicator_for(severity: Optional[str]) -> str:
    return _INDICATOR.get(str(severity or "").lower(), "warning")


def _summary(title: str) -> str:
    title = " ".join(title.split()) or "Alert"
    return title if len(title) <= 140 else title[:139].rstrip() + "…"


def _passage(c: Dict[str, Any]) -> Passage:
    meta = dict(c.get("metadata") or {})
    page = meta.get("page_number")
    return Passage(
        chunk_id=str(c.get("chunk_id") or ""),
        text=str(c.get("document") or ""),
        source_path=meta.get("source_path"),
        page_number=page if isinstance(page, int) else None,
        metadata=meta,
    )


def card_from_saved(alert: Dict[str, Any], result: Dict[str, Any], *, visit_id: str) -> Card:
    """One saved alert and its saved result (passages and explanation) as a CDS Hooks card.

    The saved alert has the fields artemis.visit_record.checks_entry gives it."""
    alert_id = alert["alert_id"]
    kind = "ai" if alert.get("source") == "ai" else "rule"
    evidence = alert.get("evidence") or {}
    severity = alert.get("severity")
    action = str(evidence.get("recommended_action") or "").strip()
    return Card(
        uuid=f"{visit_id}:{alert_id}",
        summary=_summary(alert["title"]),
        detail=alert["message"],
        indicator=indicator_for(severity),
        source=_SOURCES[kind],
        suggestions=[Suggestion(label=action, uuid=f"{visit_id}:{alert_id}:suggestion")] if action else [],
        override_reasons=OVERRIDE_CODINGS,
        extension=CardExtension(
            alert_id=alert_id,
            kind=kind,
            severity=severity,
            explanation=(result.get("explanation") or {}).get("text") or "",
            passages=[_passage(c) for c in result.get("retrieved") or []],
        ),
    )


def cards_from_entry(entry: Dict[str, Any]) -> List[Card]:
    alerts, results = entry.get("alerts") or [], entry.get("results") or []
    if len(alerts) != len(results):
        # The same check artemis.visit_record.restore makes: never show some cards and lose others.
        raise ValueError("saved results don't line up with the saved alerts")
    return [card_from_saved(a, r, visit_id=entry["visit_id"]) for a, r in zip(alerts, results)]


def plan_from_entry(entry: Dict[str, Any]) -> Optional[Plan]:
    """The plan step's result, or None when it wasn't asked for. A failed step says so, generically."""
    if not entry.get("agentic_enabled"):
        return None
    plan = entry.get("plan")
    if not isinstance(plan, dict) or "updated_management_plan_text" not in plan:
        return Plan(error="The management plan could not be produced.")
    return Plan(management_plan=plan.get("updated_management_plan_text"), issues=list(plan.get("plan_issues") or []))
