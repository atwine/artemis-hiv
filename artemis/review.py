"""Alert review and Finalize rules (moved out of app.py in fix 9), on plain decisions.

A decision is an alert's action ("Acknowledge" or "Override"), its override reason and its
comment, as the backend saves them (plan 4C.6: no longer the Streamlit screen's remembered values).
"""

from __future__ import annotations

from typing import Mapping, Sequence, Tuple

from artemis.rules.checks import Alert

# The reasons a clinician can give for overriding an alert: the design's list
# (docs/design/brief.md), owner's decision 2026-11-26 ("A, design's list").
OVERRIDE_REASONS = [
    "Already done, not documented",
    "Test not available here",
    "Not right for this patient",
    "Patient declined",
    "Will address at next visit",
    "Other (say why)",
]
OTHER_REASON = "Other (say why)"
# Decisions saved before 2026-11-26 keep the reason they were saved with. Of those, "Other"
# still needs its comment.
_NEEDS_A_COMMENT = {OTHER_REASON, "Other"}

Decision = Tuple[str, str, str]  # (action, reason, comment)


def decision_ok(action: str, reason: str, comment: str) -> bool:
    """Whether a decision settles its alert: an acknowledgement, or an override with a reason
    ("Other" also needs a comment: an override that says only "Other" can't be reviewed later,
    fix 9, D11)."""
    if action == "Acknowledge":
        return True
    if action == "Override":
        reason = (reason or "").strip()
        if reason in _NEEDS_A_COMMENT:
            return bool((comment or "").strip())
        return bool(reason)
    return False


def all_decided(alerts: Sequence[Alert], decisions: Mapping[str, Decision]) -> bool:
    """Finalize's rule: every alert has a decision that settles it (a visit with no alerts is ready)."""
    return all(a.alert_id in decisions and decision_ok(*decisions[a.alert_id]) for a in alerts)
