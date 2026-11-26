"""The words a visit's results are shown with, in one place for every screen (owner, 2026-11-26).

The Streamlit app, the FastAPI backend (Phase 4) and the Next.js site (Phase 5) all take their
wording from here, so they cannot say different things. `docs/screen-checklist.md` lists every
state a visit can end in and what the screen must show for it.
"""

from __future__ import annotations

from typing import Any, List, Optional, Tuple

from artemis.guidelines.sources import citation_name
from artemis.guidelines.vector_store import VectorSearchResult
from artemis.rules.checks import Alert
from artemis.visit import SEARCH_UNAVAILABLE

# (level, text). The level names are Streamlit's: "success" green, "info" blue, "warning" amber,
# "error" red.
Banner = Tuple[str, str]

_FAILED_REASON = {
    "failed": "the model server did not answer",
    "unreadable": "its reply could not be read as a list of alerts",
}
# The AI's reply was read only in part: the alerts read are shown, others may be missing (fix 8).
_PARTIAL_REASON = {
    "cut_off": "its reply was cut off before it finished",
    "partly_read": "part of its reply could not be read",
}
NOT_SHOWN = "not among the passages the AI was given"
DISCLAIMER = "Decision support only. Clinician retains final authority. Synthetic data only."
FINALIZE_BLOCKED = ("Finalize is disabled until all alerts are acknowledged or overridden with a reason "
                    "(the reason 'Other' needs a comment).")


def alert_heading(alert: Alert) -> str:
    """An alert's heading, saying whether the AI review or a fixed rule check raised it."""
    source = "AI review" if getattr(alert, "source", "rule") == "ai" else "Rule check"
    return f"Alert ({source}): {alert.title}"


def status_banners(status: Optional[str], screening_outcome: str, alert_count: int) -> List[Banner]:
    """The coloured banners at the top of a visit's results."""
    banners: List[Banner] = []
    if screening_outcome == "search_unavailable":
        banners.append(("error", f"{SEARCH_UNAVAILABLE}: only rule checks are shown. Check the search model setting."))
    elif screening_outcome in _FAILED_REASON:
        banners.append(
            (
                "warning",
                f"AI review failed ({_FAILED_REASON[screening_outcome]}): only rule checks are shown. "
                "Issues the AI would have raised may be missing.",
            )
        )
    elif screening_outcome in _PARTIAL_REASON:
        banners.append(
            (
                "warning",
                f"AI review incomplete ({_PARTIAL_REASON[screening_outcome]}). "
                "The AI alerts it completed are shown; others may be missing.",
            )
        )

    if status == "RED":
        banners.append(("error", f"RED: {alert_count} alert(s) to consider (at least one high/critical issue)."))
    elif status == "AMBER":
        banners.append(("warning", f"AMBER: {alert_count} alert(s) to consider."))
    elif status == "INCOMPLETE":
        banners.append(("info", "No rule check was triggered."))
    elif status == "GREEN" and screening_outcome == "ok":
        banners.append(("success", "GREEN: no alerts. The rule checks and the AI review found nothing."))
    elif status == "GREEN":
        banners.append(("info", "No rule check was triggered. The AI review was switched off for this run."))
    return banners


def citation_line(source_path: Any, page_number: Any) -> str:
    """One guideline citation: the guideline's name and its printed page (G36),
    e.g. "Uganda HIV guidelines 2022, p.255"."""
    return f"{citation_name(source_path)}, p.{page_number}"


def _unique(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        if line not in out:
            out.append(line)
    return out


def alert_references(alert: Alert, retrieved: List[VectorSearchResult]) -> Tuple[str, List[str]]:
    """(heading, lines). An AI alert lists the passages it cited; a rule alert, the passages a search found."""
    if alert.source != "ai":
        lines = [citation_line(r.metadata.get("source_path"), r.metadata.get("page_number"))
                 for r in retrieved or [] if r.metadata.get("page_number") is not None]
        return "Related passages (found by a search for this alert)", _unique(lines)

    shown = {r.chunk_id: r for r in retrieved or []}
    lines = []
    for c in (alert.evidence or {}).get("citations") or []:
        cid = str(c.get("chunk_id") or "")
        passage = shown.get(cid)
        if c.get("shown_to_ai") and passage is not None:
            lines.append(citation_line(passage.metadata.get("source_path"), passage.metadata.get("page_number")))
        else:
            # Not among the passages the AI was shown: the page is the passage's own when it is known,
            # otherwise only the AI's claim.
            page = passage.metadata.get("page_number") if passage is not None else c.get("page_number")
            lines.append(f"Guidelines, p.{page if page is not None else '?'}: {NOT_SHOWN}")
    if not lines:
        lines = ["The AI cited no guideline passage for this alert."]
    return "References (the passages the AI was shown and cited)", _unique(lines)
