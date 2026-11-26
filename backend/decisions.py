"""Acknowledge/override decisions: checking them and summing them up (plan item 4.2).

Plain functions; the route in backend/main.py only reads and saves. The rules are today's
Finalize rules from artemis/review.py, used as they are: an override needs a reason, and
"Other (say why)" needs a comment.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from artemis.review import alert_resolution_ok, can_finalize, decisions_from_state
from artemis.rules.checks import Alert
from backend.models import DecisionIn, DecisionOut


class BadDecision(ValueError):
    """A decision that can't be saved; the message is safe to show."""


def decision_rows(alerts: Sequence[Alert], decisions: Sequence[DecisionIn]) -> List[Dict[str, Any]]:
    """The rows to save for these decisions, or BadDecision if any one of them is wrong (then
    none is saved). An alert decided twice in one request keeps the last decision."""
    by_id = {a.alert_id: a for a in alerts}
    state: Dict[str, Any] = {}
    for d in decisions:
        if d.alert_id not in by_id:
            raise BadDecision("An alert in the request isn't in this visit.")
        # The same keys the Streamlit screen uses, so the rules in artemis/review.py read them.
        state[f"alert_action_{d.alert_id}"] = d.action
        state[f"alert_override_reason_{d.alert_id}"] = d.reason or ""
        state[f"alert_override_comment_{d.alert_id}"] = d.comment
        if not alert_resolution_ok(state, d.alert_id):
            raise BadDecision("An override needs a reason, and 'Other (say why)' needs a comment.")
    chosen = [by_id[i] for i in dict.fromkeys(d.alert_id for d in decisions)]
    return decisions_from_state(state, chosen)


def ready_to_finalize(alerts: Sequence[Alert], latest: Mapping[str, DecisionOut]) -> bool:
    """Today's Finalize rule (artemis.review.can_finalize) on the latest saved decisions."""
    state: Dict[str, Any] = {"analysis_ran": True}
    for alert_id, d in latest.items():
        state[f"alert_action_{alert_id}"] = d.action
        state[f"alert_override_reason_{alert_id}"] = d.reason
        state[f"alert_override_comment_{alert_id}"] = d.comment
    return can_finalize(state, list(alerts))


def summary(alert_ids: Sequence[str], latest: Mapping[str, DecisionOut]) -> Tuple[List[DecisionOut], List[str]]:
    """The latest decision on each decided alert, and the alerts still undecided, in alert order."""
    return [latest[a] for a in alert_ids if a in latest], [a for a in alert_ids if a not in latest]
