"""Alert review and Finalize rules (moved out of app.py in fix 9)."""

from __future__ import annotations

from typing import Any, List, Mapping

from artemis.rules.checks import Alert


def alert_resolution_ok(state: Mapping[str, Any], alert_id: str) -> bool:
    action = state.get(f"alert_action_{alert_id}")
    if action == "Acknowledge":
        return True

    if action == "Override":
        reason = (state.get(f"alert_override_reason_{alert_id}") or "").strip()
        return bool(reason)

    return False


def can_finalize(state: Mapping[str, Any], alerts: List[Alert]) -> bool:
    if not state.get("analysis_ran", False):
        return False

    if not alerts:
        return True

    return all(alert_resolution_ok(state, a.alert_id) for a in alerts)
