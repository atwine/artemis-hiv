"""What the screen remembers about the last analysis, and when to forget it.

Streamlit keeps values between clicks in `st.session_state`, a dict-like store. A result
belongs to one patient and one note. It must not be shown after the clinician picks another
patient. When the note changes, the screen says so (see `note_changed`).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, MutableMapping

# Every value the last analysis leaves behind, with its "nothing has run" value.
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

# Per-alert review choices and timings are stored under these prefixes plus the alert id.
_PER_ALERT_PREFIXES = ("alert_action_", "alert_override_reason_", "alert_override_comment_")


def init_analysis_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ANALYSIS_DEFAULTS.items():
        state.setdefault(key, copy.deepcopy(value))


def clear_analysis(state: MutableMapping[str, Any]) -> None:
    """Forget the last analysis completely, including the review of each alert."""
    for key in [k for k in list(state.keys()) if str(k).startswith(_PER_ALERT_PREFIXES)]:
        del state[key]
    for key, value in ANALYSIS_DEFAULTS.items():
        state[key] = copy.deepcopy(value)


def analysis_belongs_to(state: MutableMapping[str, Any], patient_id: str) -> bool:
    """True when nothing has run, or the last run was for this patient."""
    return not state.get("analysis_ran") or state.get("analysis_patient_id") == patient_id


def note_changed(state: MutableMapping[str, Any], current_note: str) -> bool:
    """True when the shown results were produced from a different note than the one on screen."""
    return bool(state.get("analysis_ran")) and (state.get("analysis_note") or "") != (current_note or "")
