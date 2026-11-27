"""Acknowledge/override decisions: checking them and summing them up (plan item 4.2).

Plain functions; the route in backend/main.py only reads and saves. The rules are the Finalize
rules in artemis/review.py: an override needs a reason, and "Other (say why)" needs a comment.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence, Tuple

from artemis.review import all_decided, decision_ok
from artemis.rules.checks import Alert
from backend.models import DecisionIn, DecisionOut


class BadDecision(ValueError):
    """A decision that can't be saved; the message is safe to show."""


def decision_rows(alerts: Sequence[Alert], decisions: Sequence[DecisionIn]) -> List[Dict[str, Any]]:
    """The rows to save for these decisions, or BadDecision if any one of them is wrong (then
    none is saved). An alert decided twice in one request keeps the last decision."""
    by_id = {a.alert_id: a for a in alerts}
    rows: Dict[str, Dict[str, Any]] = {}
    for d in decisions:
        if d.alert_id not in by_id:
            raise BadDecision("An alert in the request isn't in this visit.")
        if not decision_ok(d.action, d.reason or "", d.comment):
            raise BadDecision("An override needs a reason, and 'Other (say why)' needs a comment.")
        a, override = by_id[d.alert_id], d.action == "Override"
        rows[d.alert_id] = {
            "alert_id": a.alert_id, "source": a.source, "title": a.title,
            "severity": (a.evidence or {}).get("severity"), "action": d.action,
            "reason": (d.reason or "").strip() if override else "",
            "comment": d.comment.strip() if override else "",
        }
    return list(rows.values())


def ready_to_finalize(alerts: Sequence[Alert], latest: Mapping[str, DecisionOut]) -> bool:
    """Finalize's rule (artemis.review.all_decided) on the latest saved decisions."""
    return all_decided(list(alerts), {a: (d.action, d.reason, d.comment) for a, d in latest.items()})


def summary(alert_ids: Sequence[str], latest: Mapping[str, DecisionOut]) -> Tuple[List[DecisionOut], List[str]]:
    """The latest decision on each decided alert, and the alerts still undecided, in alert order."""
    return [latest[a] for a in alert_ids if a in latest], [a for a in alert_ids if a not in latest]
