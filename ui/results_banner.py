"""The coloured banners at the top of the Results section."""

from __future__ import annotations

from typing import List, Optional, Tuple

# (Streamlit call name, text): "success" is green, "info" blue, "warning" amber, "error" red.
Banner = Tuple[str, str]

_FAILED_REASON = {
    "failed": "the model server did not answer",
    "unreadable": "its reply could not be read as a list of alerts",
}


def status_banners(status: Optional[str], screening_outcome: str, alert_count: int) -> List[Banner]:
    banners: List[Banner] = []
    if screening_outcome in _FAILED_REASON:
        banners.append(
            (
                "warning",
                f"AI review failed ({_FAILED_REASON[screening_outcome]}): only rule checks are shown. "
                "Issues the AI would have raised may be missing.",
            )
        )

    if status == "RED":
        banners.append(("error", f"RED: {alert_count} alert(s) to consider (at least one high/critical issue)."))
    elif status == "YELLOW":
        banners.append(("warning", f"YELLOW: {alert_count} alert(s) to consider."))
    elif status == "INCOMPLETE":
        banners.append(("info", "No rule check was triggered."))
    elif status == "GREEN" and screening_outcome == "ok":
        banners.append(("success", "GREEN: no alerts. The rule checks and the AI review found nothing."))
    elif status == "GREEN":
        banners.append(("info", "No rule check was triggered. The AI review was switched off for this run."))
    return banners
