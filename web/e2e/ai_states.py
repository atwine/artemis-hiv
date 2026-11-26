"""The status and banners the API would send for each way an AI review can end badly, for the
screenshots of those states (e2e/screens.spec.ts). Built with the backend's own functions, so the
wording is the API's; nothing calls a model.

Usage: python e2e/ai_states.py '<JSON list of the alerts' severities, null for none>'
Prints {outcome: {"status": ..., "banners": [{"level": ..., "text": ...}]}}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from artemis.rules.checks import Alert  # noqa: E402
from artemis.screen_text import status_banners  # noqa: E402
from artemis.visit import compute_overall_status  # noqa: E402

OUTCOMES = ("search_unavailable", "failed", "unreadable", "cut_off", "partly_read")


def main() -> None:
    severities = json.loads(sys.argv[1])
    alerts = [Alert(alert_id=f"a{i}", title="", message="", evidence={"severity": s} if s else {}, query_hint="")
              for i, s in enumerate(severities)]
    out = {}
    for outcome in OUTCOMES:
        status = compute_overall_status(alerts, outcome)
        out[outcome] = {
            "status": status,
            "banners": [{"level": level, "text": text} for level, text in status_banners(status, outcome, len(alerts))],
        }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
