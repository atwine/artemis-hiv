"""Alert review and Finalize rules (moved out of app.py in fix 9)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from artemis.rules.checks import Alert

# The reasons a clinician can give for overriding an alert (the Streamlit screen and the backend).
OVERRIDE_REASONS = ["Already addressed", "Not applicable", "Will address later", "Patient declined", "Other"]


def alert_resolution_ok(state: Mapping[str, Any], alert_id: str) -> bool:
    action = state.get(f"alert_action_{alert_id}")
    if action == "Acknowledge":
        return True

    if action == "Override":
        reason = (state.get(f"alert_override_reason_{alert_id}") or "").strip()
        if reason == "Other":
            # An override that says only "Other" can't be reviewed later (fix 9, D11).
            return bool((state.get(f"alert_override_comment_{alert_id}") or "").strip())
        return bool(reason)

    return False


def can_finalize(state: Mapping[str, Any], alerts: List[Alert]) -> bool:
    if not state.get("analysis_ran", False):
        return False

    if not alerts:
        return True

    return all(alert_resolution_ok(state, a.alert_id) for a in alerts)


def decisions_from_state(state: Mapping[str, Any], alerts: List[Alert]) -> List[Dict[str, Any]]:
    """The clinician's decision on each alert, as saved in the visit record at Finalize (fix 9)."""
    out: List[Dict[str, Any]] = []
    for a in alerts:
        action = state.get(f"alert_action_{a.alert_id}") or "Unreviewed"
        override = action == "Override"
        out.append(
            {
                "alert_id": a.alert_id,
                "source": a.source,
                "title": a.title,
                "severity": (a.evidence or {}).get("severity"),
                "action": action,
                "reason": (state.get(f"alert_override_reason_{a.alert_id}") or "").strip() if override else "",
                "comment": (state.get(f"alert_override_comment_{a.alert_id}") or "").strip() if override else "",
            }
        )
    return out
