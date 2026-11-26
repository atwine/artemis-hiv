"""What the screen remembers about the last analysis, and when to forget it.

Streamlit keeps values between clicks in `st.session_state`, a dict-like store. A result
belongs to one patient and one note. It must not be shown after the clinician picks another
patient. When the note changes, the screen says so (see `note_changed`).
"""

from __future__ import annotations

import copy
from typing import Any, MutableMapping

# Every value the screen remembers is named in artemis/session_keys.py (plan item 4.6).
from artemis.session_keys import ANALYSIS_DEFAULTS, PER_ALERT_PREFIXES




def init_analysis_state(state: MutableMapping[str, Any]) -> None:
    for key, value in ANALYSIS_DEFAULTS.items():
        state.setdefault(key, copy.deepcopy(value))


def clear_analysis(state: MutableMapping[str, Any]) -> None:
    """Forget the last analysis completely, including the review of each alert."""
    for key in [k for k in list(state.keys()) if str(k).startswith(PER_ALERT_PREFIXES)]:
        del state[key]
    for key, value in ANALYSIS_DEFAULTS.items():
        state[key] = copy.deepcopy(value)


def analysis_belongs_to(state: MutableMapping[str, Any], patient_id: str) -> bool:
    """True when nothing has run, or the last run was for this patient."""
    return not state.get("analysis_ran") or state.get("analysis_patient_id") == patient_id


def note_changed(state: MutableMapping[str, Any], current_note: str) -> bool:
    """True when the shown results were produced from a different note than the one on screen."""
    return bool(state.get("analysis_ran")) and (state.get("analysis_note") or "") != (current_note or "")
