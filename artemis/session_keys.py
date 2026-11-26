"""The names of everything the Streamlit screen remembers about a visit, in one place (plan 4.6).

`ANALYSIS_DEFAULTS` lists each visit-level value with its "nothing has run" value; the key
functions name the per-alert values. The screen (app.py, ui/state.py), reopening a saved visit
(artemis/visit_record.py), the Finalize rules (artemis/review.py) and the backend's decision
checks (backend/decisions.py) all take the names from here. tests/test_session_keys.py fails if
a file spells one out by hand. The names are the ones saved screens already use.
"""

from __future__ import annotations

from typing import Any, Dict

ANALYSIS_DEFAULTS: Dict[str, Any] = {
    "analysis_ran": False,
    "analysis_patient_id": None,
    "analysis_note": None,
    "finalized": False,
    "analysis_status": None,
    "analysis_screening_outcome": "not_run",
    "analysis_alerts": [],
    "analysis_results": [],
    "analysis_ollama_error": None,
    "analysis_screening_debug": None,
    "analysis_patient_summary": None,
    "agentic_debug_enabled": False,
    "agentic_debug_result": None,
    "agentic_debug_reasoner": None,
    # The visit record (fix 9): this run's id and save time, whether it was reopened from the
    # record, whether saving failed, and when it was finalized.
    "analysis_visit_id": None,
    "analysis_saved_at": None,
    "analysis_restored": False,
    "analysis_record_error": False,
    "analysis_finalized_at": None,
}

_ACTION = "alert_action_"
_REASON = "alert_override_reason_"
_COMMENT = "alert_override_comment_"
_SAVED_REASON = "alert_saved_reason_"
# Every per-alert value starts with one of these, then the alert's id.
PER_ALERT_PREFIXES = (_ACTION, _REASON, _COMMENT, _SAVED_REASON)


def action_key(alert_id: str) -> str:
    """The clinician's choice on an alert: Unreviewed, Acknowledge or Override."""
    return f"{_ACTION}{alert_id}"


def reason_key(alert_id: str) -> str:
    """The override reason picked for an alert."""
    return f"{_REASON}{alert_id}"


def comment_key(alert_id: str) -> str:
    """The override comment written for an alert."""
    return f"{_COMMENT}{alert_id}"


def saved_reason_key(alert_id: str) -> str:
    """The reason a reopened visit was saved with, so the picker keeps offering an older one."""
    return f"{_SAVED_REASON}{alert_id}"
