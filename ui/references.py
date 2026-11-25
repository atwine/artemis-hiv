"""The References list under each alert (fix 8)."""

from __future__ import annotations

from typing import Any, List, Tuple

from artemis.rules.checks import Alert
from artemis.guidelines.vector_store import VectorSearchResult

NOT_SHOWN = "not among the passages the AI was given"


def _unique(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines:
        if line not in out:
            out.append(line)
    return out


def alert_references(alert: Alert, retrieved: List[VectorSearchResult]) -> Tuple[str, List[str]]:
    """(heading, lines). An AI alert lists the passages it cited; a rule alert, the passages a search found."""
    if alert.source != "ai":
        pages = [r.metadata.get("page_number") for r in retrieved or []]
        lines = [f"Guidelines, p.{p}" for p in pages if p is not None]
        return "Related passages (found by a search for this alert)", _unique(lines)

    pages_by_id = {r.chunk_id: r.metadata.get("page_number") for r in retrieved or []}
    lines = []
    for c in (alert.evidence or {}).get("citations") or []:
        cid = str(c.get("chunk_id") or "")
        page: Any = pages_by_id.get(cid, c.get("page_number"))
        if c.get("shown_to_ai") and cid in pages_by_id:
            lines.append(f"Guidelines, p.{page}")
        else:
            lines.append(f"Guidelines, p.{page if page is not None else '?'}: {NOT_SHOWN}")
    if not lines:
        lines = ["The AI cited no guideline passage for this alert."]
    return "References (the passages the AI was shown and cited)", _unique(lines)
