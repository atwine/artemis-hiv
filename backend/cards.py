"""Turn a saved visit check into what the screen gets: CDS Hooks cards, the plan and the
screen's wording.

Plain functions over the "checks_run" entry that backend/records.py checks_entry builds (the
same dict that is saved), so a visit reads the same whether it just ran or was saved earlier.
All wording comes from artemis/screen_text.py (plan item 4.7, docs/screen-checklist.md); the
website only displays it.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, List, Optional

from artemis.guidelines.vector_store import VectorSearchResult
from artemis.review import OVERRIDE_REASONS
from artemis.rules.checks import Alert
from artemis.patient.labs import LabEntry
from backend.records import saved_alerts
from artemis.screen_text import (
    alert_heading,
    alert_references,
    alert_values,
    record_banners,
    citation_line,
    key_sentence,
    plain_explanation,
    status_banners,
)
from backend.models import AlertValue, Banner, Card, CardExtension, Coding, Passage, Source, Suggestion

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


def card_from_saved(alert: Alert, retrieved: List[VectorSearchResult], explanation: str, *, severity: Optional[str],
                    visit_id: str, values: Optional[List[dict]] = None) -> Card:
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
            values=[AlertValue(**v) for v in values or []],
            key_sentence=key_sentence(alert, retrieved),
        ),
    )


def cards_from_entry(entry: Dict[str, Any], labs: Optional[List[LabEntry]] = None) -> List[Card]:
    """The saved visit check's alerts as cards (backend/records.py saved_alerts): results that
    don't line up with the alerts raise ValueError rather than show some cards and lose others."""
    visit_date = _date(entry.get("visit_date"))
    return [
        card_from_saved(
            s.alert, s.retrieved, plain_explanation(s.explanation), severity=s.severity, visit_id=entry["visit_id"],
            values=alert_values(s.alert, labs, visit_date) if labs and visit_date else [],
        )
        for s in saved_alerts(entry)
    ]


def _date(text: Any) -> Optional[datetime.date]:
    try:
        return datetime.date.fromisoformat(str(text))
    except ValueError:
        return None


def banners_for(entry: Dict[str, Any], *, record_saved: bool = True) -> List[Banner]:
    """The coloured banners above the results (docs/screen-checklist.md sections 1, 2 and 4)."""
    found = status_banners(entry["status"], entry["ai_review"], len(entry.get("alerts") or []))
    return [Banner(level=level, text=text) for level, text in found + record_banners(saved=record_saved)]
