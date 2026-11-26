"""Every way the AI review can end, and every overall status, in one small place.

The API and the screens are built from these lists, and artemis.visit.AnalysisResult refuses
any other value (docs/screen-checklist.md). artemis/visit.py re-exports them. They live in
this file, with no other imports, so a script can read them without loading the AI libraries
(owner, 2026-11-26).
"""

from __future__ import annotations

from typing import Optional

AI_REVIEW_OUTCOMES = ("not_run", "ok", "failed", "unreadable", "cut_off", "partly_read", "search_unavailable")
STATUSES = ("GREEN", "AMBER", "RED", "INCOMPLETE")

# The owner renamed YELLOW to AMBER everywhere (2026-11-26, "Amber everywhere"). Saved records
# are never rewritten, so anything that reads an older one goes through status_name.
_OLD_STATUS_NAMES = {"YELLOW": "AMBER"}


def status_name(value: Optional[str]) -> Optional[str]:
    """A saved status in today's name: YELLOW, from older records, reads as AMBER."""
    return _OLD_STATUS_NAMES.get(value, value) if value is not None else None
