from __future__ import annotations

import datetime as dt

from artemis.patient.labs import lab_rows_to_entries
from tests import pipeline_harness as h
from ui.labs import editor_rows, lab_rows_for_display


def test_table_rows_become_plain_text_and_blank_rows_are_skipped() -> None:
    rows = editor_rows(
        [
            {"test": "creatinine", "date": dt.date(2025, 10, 1), "value": 1.4, "unit": "mg/dL"},
            {"test": None, "date": None, "value": float("nan"), "unit": None},
        ]
    )
    assert rows[0] == {"test": "creatinine", "date": "2025-10-01", "value": "1.4", "unit": "mg/dL"}
    entries, errors = lab_rows_to_entries(rows, source="previous")
    assert errors == []
    assert entries == {"creatinine": [{"date": "2025-10-01", "value": "1.4", "unit": "mg/dL", "source": "previous"}]}


def test_patient_details_show_structured_results_split_by_today_and_earlier() -> None:
    p2 = next(p for p in h.patients() if p["patient_id"] == "P002")
    visit = dt.date(2026, 1, 22)
    assert lab_rows_for_display(p2, visit, today=True) == []
    earlier = lab_rows_for_display(p2, visit, today=False)
    assert {"Test": "creatinine", "Result": "76 umol/L", "Date": "2025-12-15", "Days before visit": "38"} in earlier
    assert len(earlier) == 3
