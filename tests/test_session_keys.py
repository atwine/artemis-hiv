"""The screen's remembered values are named in one place, artemis/session_keys.py (plan item 4.6).

Before, the same key names were typed out in app.py, ui/state.py, artemis/visit_record.py,
artemis/review.py and backend/decisions.py, so a renamed key could be missed in one of them.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_key_restore_gives_back_is_a_known_one() -> None:
    from artemis import visit_record
    from artemis.session_keys import ANALYSIS_DEFAULTS, PER_ALERT_PREFIXES

    alert = {"alert_id": "A1", "title": "t", "message": "m", "evidence": {}, "query_hint": "", "source": "rule"}
    checks = {"event": "checks_run", "patient_id": "P1", "visit_id": "v", "status": "AMBER",
              "alerts": [alert], "results": [{"retrieved": [], "explanation": {"text": ""}}]}
    finalized = {"event": "finalized", "visit_id": "v", "patient_id": "P1", "saved_at": "2026-11-20T08:00:00+00:00",
                 "decisions": [{"alert_id": "A1", "action": "Acknowledge", "reason": "", "comment": ""}]}
    for key in visit_record.restore(checks, finalized):
        assert key in ANALYSIS_DEFAULTS or key.startswith(PER_ALERT_PREFIXES), key


def test_every_visit_key_the_app_sets_is_a_known_one() -> None:
    from artemis.session_keys import ANALYSIS_DEFAULTS

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    set_keys = set(re.findall(r'st\.session_state\["((?:analysis_|agentic_debug_)[a-z_]*|finalized)"\]\s*=', source))
    assert set_keys and set_keys <= set(ANALYSIS_DEFAULTS), set_keys - set(ANALYSIS_DEFAULTS)


def test_per_alert_keys_are_spelled_only_in_one_place() -> None:
    from artemis.session_keys import PER_ALERT_PREFIXES

    for path in [ROOT / "app.py", *(ROOT / "artemis").rglob("*.py"), *(ROOT / "ui").rglob("*.py"), *(ROOT / "backend").rglob("*.py")]:
        if path.name == "session_keys.py":
            continue
        text = path.read_text(encoding="utf-8")
        for prefix in PER_ALERT_PREFIXES:
            assert prefix not in text, f"{path.relative_to(ROOT)} spells {prefix!r}; use artemis.session_keys"


def test_the_key_names_are_the_ones_saved_screens_already_use() -> None:
    """The names themselves don't change, so a reopened visit and the Streamlit widgets still match."""
    from artemis.session_keys import action_key, comment_key, reason_key, saved_reason_key

    assert (action_key("A1"), reason_key("A1"), comment_key("A1"), saved_reason_key("A1")) == (
        "alert_action_A1", "alert_override_reason_A1", "alert_override_comment_A1", "alert_saved_reason_A1")
