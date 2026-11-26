"""The words a visit's results are shown with, in one place for every screen (owner, 2026-11-26).

The Streamlit app, the FastAPI backend (Phase 4) and the Next.js site (Phase 5) all take their
wording from here, so they cannot say different things. `docs/screen-checklist.md` lists every
state a visit can end in and what the screen must show for it.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, List, Optional, Tuple

from artemis.guidelines.sources import citation_name
from artemis.patient.labs import TEST_NAMES, LabEntry, latest_entries
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
                    "(the reason 'Other (say why)' needs a comment).")


# Citation fragments some texts carry inline: "[chunk_id: x, page_number: 3]", "(page=3)", "chunk_id: x".
_INLINE_CITATIONS = (
    re.compile(r"\[\s*chunk_id\s*:\s*[^\],]+\s*,\s*page_number\s*:\s*(\d+)\s*\]", re.IGNORECASE),
    re.compile(r"\(page\s*=\s*\d+\)", re.IGNORECASE),
    re.compile(r"chunk[_\s]*id\s*[:=]\s*[^\s,\)\]]+", re.IGNORECASE),
)


def plain_text(text: Any) -> str:
    """A text without inline citation fragments; the references are listed apart."""
    out = str(text or "")
    for pattern in _INLINE_CITATIONS:
        out = pattern.sub("", out)
    return out.strip()


def plain_explanation(text: Any) -> str:
    """An alert's explanation as the screen shows it: the reason alone, without the "Patient
    evidence" dump or the "Guideline excerpts" that follow it (moved here from app.py so the API
    sends the same text, owner 2026-11-26)."""
    out = re.sub(r"^\s*why this alert\s*:\s*", "", plain_text(text), flags=re.IGNORECASE)
    out = re.split(r"\bpatient evidence\s*:\s*", out, maxsplit=1, flags=re.IGNORECASE)[0]
    out = re.split(r"\bguideline excerpts\s*:\s*", out, maxsplit=1, flags=re.IGNORECASE)[0]
    return out.strip()


# The value box (owner, 2026-11-26: by code, no AI change). The lab tests each fixed rule is
# about; any other alert's tests are the ones its own title and message name.
RULE_TESTS = {
    "tdf_creatinine_overdue": ["creatinine", "egfr"],
    "tdf_creatinine_missing": ["creatinine", "egfr"],
    "tdf_creatinine_pasted_only": ["creatinine", "egfr"],
}
_TEST_WORDS = [
    ("viral_load", r"viral\s+load|\bVL\b"), ("cd4", r"\bCD4\b"), ("creatinine", r"creatinine"),
    ("egfr", r"\beGFR\b"), ("hemoglobin", r"ha?emoglobin|\bHb\b"), ("alt", r"\bALT\b"),
    ("fasting_glucose", r"glucose"), ("hba1c", r"\bHbA1c\b"), ("total_cholesterol", r"total\s+cholesterol"),
    ("ldl", r"\bLDL\b"), ("hdl", r"\bHDL\b"), ("triglycerides", r"triglyceride"),
]


def alert_values(alert: Alert, labs: List[LabEntry], visit_date: datetime.date) -> List[dict]:
    """The patient values an alert is about, each as recorded (label, value, unit, date): the
    latest result of each test on or before the visit date. None when no test is named."""
    text = f"{alert.title} {alert.message}"
    tests = RULE_TESTS.get(alert.alert_id) or [t for t, words in _TEST_WORDS if re.search(words, text, re.IGNORECASE)]
    latest = latest_entries(labs, visit_date)
    return [
        {"label": TEST_NAMES.get(t, t), "value": latest[t].value, "unit": latest[t].unit, "date": latest[t].date.isoformat()}
        for t in tests if t in latest
    ]


def _words(text: str) -> set:
    text = re.sub(r"\bVL\b", "viral load", text)  # the guidelines' shorthand
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 3}


# Where a passage's text breaks into pieces: sentence ends, line breaks, bullets (" - "),
# footnote stars and flowchart labels (" : ").
_PIECES = re.compile(r"(?<=[.!?])\s+|\n+|\s+-\s+|\*+|\s+:\s+")


def key_sentence(alert: Alert, passages: List[VectorSearchResult]) -> Optional[str]:
    """The one guideline sentence that matters most for an alert (owner, 2026-11-26: by code): from
    the alert's passages, the piece sharing the most words with the alert's title and message,
    the first one on a tie. Table rows, headings in capitals, and pieces under 25 or over 300
    characters are skipped; None when nothing shares at least two words."""
    wanted = _words(f"{alert.title} {alert.message}")
    best, best_score = None, 1
    for p in passages:
        for piece in _PIECES.split(p.document or ""):
            piece = piece.strip(" ;,")
            letters = [c for c in piece if c.isalpha()]
            if "|" in piece or not 25 <= len(piece) <= 300 or (letters and sum(c.isupper() for c in letters) > 0.6 * len(letters)):
                continue
            score = len(wanted & _words(piece))
            if score > best_score:
                best, best_score = piece, score
    return best


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
    e.g. "Uganda HIV Guidelines 2022 · p. 255" (the design's look, owner 2026-11-26)."""
    return f"{citation_name(source_path)} · p. {page_number}"


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
            lines.append(f"Guidelines · p. {page if page is not None else '?'}: {NOT_SHOWN}")
    if not lines:
        lines = ["The AI cited no guideline passage for this alert."]
    return "References (the passages the AI was shown and cited)", _unique(lines)
