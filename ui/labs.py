"""Lab results on the screen: the add-case tables, and the Patient Details list."""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

from artemis.patient.labs import TEST_NAMES, read_lab_entries

LAB_COLUMNS = ["test", "date", "value", "unit"]


def _cell(value: Any) -> str:
    """A table cell as text: empty for blanks, YYYY-MM-DD for dates."""
    if value is None:
        return ""
    if isinstance(value, (_dt.date, _dt.datetime)):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "strftime"):  # pandas Timestamp
        return value.strftime("%Y-%m-%d")
    text = str(value).strip()
    return "" if text.lower() in {"nan", "nat", "none"} else text


def editor_rows(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """The add-case table's rows as plain text, ready for artemis.patient.labs.lab_rows_to_entries."""
    return [{col: _cell(r.get(col)) for col in LAB_COLUMNS} for r in records or []]


def lab_rows_for_display(patient: Dict[str, Any], visit_date: _dt.date, *, today: bool) -> List[Dict[str, str]]:
    """Results for the Patient Details list: today's (entered as today's, or dated on the visit) or earlier ones."""
    rows: List[Dict[str, str]] = []
    for e in read_lab_entries(patient):
        is_today = e.source == "today" or (e.source == "record" and e.date == visit_date)
        if is_today != today:
            continue
        days = (visit_date - e.date).days
        rows.append(
            {
                "Test": TEST_NAMES.get(e.test, e.test.replace("_", " ")),
                "Result": f"{e.value} {e.unit}".strip(),
                "Date": e.date.isoformat(),
                "Days before visit": str(days),
            }
        )
    return rows
