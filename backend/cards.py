"""Turn a saved visit check into what the screen gets: CDS Hooks cards, the plan and the
screen's wording.

Plain functions over the "checks_run" entry that artemis.visit_record.checks_entry builds (the
same dict that is saved), so a visit reads the same whether it just ran or was saved earlier.
All wording comes from artemis/screen_text.py (plan item 4.7, docs/screen-checklist.md); the
website only displays it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from artemis import visit_record
from artemis.guidelines.vector_store import VectorSearchResult
from artemis.review import OVERRIDE_REASONS
from artemis.rules.checks import Alert
from artemis.screen_text import alert_heading, alert_references, citation_line, status_banners
from backend.models import Banner, Card, CardExtension, Coding, Passage, Plan, Source, Suggestion

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


def _passage(r: VectorSearchResult) -> Passage:
    page = r.metadata.get("page_number")
    page = page if isinstance(page, int) else None
    return Passage(
        chunk_id=r.chunk_id,
        text=r.document,
        source_path=r.metadata.get("source_path"),
        page_number=page,
        citation=citation_line(r.metadata.get("source_path"), page) if page is not None else None,
        metadata=dict(r.metadata),
    )


def card_from_saved(alert: Alert, retrieved: List[VectorSearchResult], explanation: str, *, severity: Optional[str], visit_id: str) -> Card:
    """One alert, its passages and its explanation as a CDS Hooks card."""
    kind = "ai" if alert.source == "ai" else "rule"
    action = str((alert.evidence or {}).get("recommended_action") or "").strip()
    references_heading, references = alert_references(alert, retrieved)
    return Card(
        uuid=f"{visit_id}:{alert.alert_id}",
        summary=_summary(alert.title),
        detail=alert.message,
        indicator=indicator_for(severity),
        source=_SOURCES[kind],
        suggestions=[Suggestion(label=action, uuid=f"{visit_id}:{alert.alert_id}:suggestion")] if action else [],
        override_reasons=OVERRIDE_CODINGS,
        extension=CardExtension(
            alert_id=alert.alert_id,
            kind=kind,
            severity=severity,
            explanation=explanation,
            passages=[_passage(r) for r in retrieved],
            heading=alert_heading(alert),
            references_heading=references_heading,
            references=references,
        ),
    )


def cards_from_entry(entry: Dict[str, Any]) -> List[Card]:
    """The saved visit check's alerts as cards. Read back through artemis.visit_record.restore,
    the check the Streamlit app reopens a visit with: results that don't line up with the alerts
    raise ValueError rather than show some cards and lose others."""
    restored = visit_record.restore(entry)
    severities = [a.get("severity") for a in entry.get("alerts") or []]
    return [
        card_from_saved(r["alert"], r["retrieved"], r["explanation"].text, severity=sev, visit_id=entry["visit_id"])
        for r, sev in zip(restored["analysis_results"], severities)
    ]


def banners_for(entry: Dict[str, Any]) -> List[Banner]:
    """The coloured banners above the results (docs/screen-checklist.md sections 1 and 2)."""
    return [
        Banner(level=level, text=text)
        for level, text in status_banners(entry["status"], entry["ai_review"], len(entry.get("alerts") or []))
    ]


def plan_from_entry(entry: Dict[str, Any]) -> Optional[Plan]:
    """The plan step's result. None when it wasn't asked for, or didn't run because the guideline
    search was unavailable (the red banner says why, as on the Streamlit screen). A step that ran
    and failed says so, generically."""
    plan = entry.get("plan")
    if not entry.get("agentic_enabled") or plan is None:
        return None
    if not isinstance(plan, dict) or "updated_management_plan_text" not in plan:
        return Plan(error="The management plan could not be produced.")
    return Plan(management_plan=plan.get("updated_management_plan_text"), issues=list(plan.get("plan_issues") or []))
