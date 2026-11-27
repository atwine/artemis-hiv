"""The alert review and Finalize rules (fix 9, owner 2026-11-26), on plain decisions.

Plan 4C.6: the rules no longer read the Streamlit screen's remembered values; they take each
decision's action, reason and comment, as the backend saves them.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from artemis.review import OTHER_REASON, OVERRIDE_REASONS, all_decided, decision_ok
from artemis.rules.checks import Alert

ROOT = Path(__file__).resolve().parents[1]


def _alert(alert_id: str) -> Alert:
    return Alert(alert_id=alert_id, title="t", message="m", evidence={}, query_hint="", source="rule")


@pytest.mark.parametrize("action, reason, comment, ok", [
    ("Acknowledge", "", "", True),
    ("Override", "Already done, not documented", "", True),
    ("Override", "", "", False),  # an override needs a reason
    ("Override", "  ", "", False),
    ("Override", "Other (say why)", "  ", False),  # "Other" needs a comment
    ("Override", "Other (say why)", "Done at another clinic last week.", True),
    ("Override", "Other", "", False),  # an older "Other" still needs its comment
    ("Unreviewed", "", "", False),
])
def test_what_counts_as_a_decided_alert(action, reason, comment, ok):
    assert decision_ok(action, reason, comment) is ok


def test_the_override_reasons_are_the_designs_list():
    """Owner, 2026-11-26 ("A, design's list"): the list in docs/design/brief.md, in its order."""
    brief = (ROOT / "docs" / "design" / "brief.md").read_text(encoding="utf-8")
    proposed = re.search(r"Proposed: (.*?)(?:\r?\n){2}", brief, re.S).group(1)
    assert OVERRIDE_REASONS == [r.strip() for r in " ".join(proposed.split()).rstrip(".").split(" · ")]
    assert OVERRIDE_REASONS[-1] == OTHER_REASON == "Other (say why)"


def test_a_visit_is_ready_once_every_alert_is_decided():
    alerts = [_alert("A1"), _alert("A2")]
    assert all_decided([], {})  # nothing to decide
    assert not all_decided(alerts, {"A1": ("Acknowledge", "", "")})
    assert not all_decided(alerts, {"A1": ("Acknowledge", "", ""), "A2": ("Override", "", "")})
    assert all_decided(alerts, {"A1": ("Acknowledge", "", ""), "A2": ("Override", "Patient declined", "")})
