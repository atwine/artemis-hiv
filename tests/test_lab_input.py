"""Fix 4: labs reach the model and the rules with unit, date, age and source; notes are dated."""

from __future__ import annotations

import copy
from typing import List

import pytest

from artemis.patient.record import build_patient_context, days_since_lab
from artemis.patient.summary import build_stage1_summary
from modules.llm_screening import generate_llm_screening_alerts
from tests import pipeline_harness as h


class RecordingModel:
    model = "stub"
    last_error = None

    def __init__(self) -> None:
        self.messages: List[dict] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.messages = messages
        return "[]"


def _patient(pid: str) -> dict:
    return copy.deepcopy(next(p for p in h.patients() if p["patient_id"] == pid))


def _model_input(pid: str) -> str:
    p = _patient(pid)
    ctx = build_patient_context(p)
    model = RecordingModel()
    generate_llm_screening_alerts(
        patient_context=ctx,
        stage1_summary=build_stage1_summary(patient=p, context=ctx),
        screening_chunks=[],
        llm_client=model,
        debug={},
    )
    return next(m["content"] for m in model.messages if m["role"] == "user")


def test_structured_labs_reach_the_model_with_unit_date_and_age() -> None:
    text = _model_input("P002")
    assert "None recorded" not in text
    assert "creatinine 76 umol/L on 2025-12-15 (38 days before the visit)" in text
    assert "viral load 20 copies/mL on 2025-09-15 (129 days before the visit)" in text


def test_the_app_works_out_how_old_each_result_is() -> None:
    assert "viral load 40 copies/mL on 2025-10-01 (113 days before the visit)" in _model_input("P001")
    p = _patient("P001")
    latest = build_stage1_summary(patient=p, context=build_patient_context(p))["latest_labs"]
    assert latest["viral_load"]["unit"] == "copies/mL"
    assert latest["viral_load"]["days_before_visit"] == 113


def test_todays_note_is_labelled_apart_from_earlier_visits() -> None:
    text = _model_input("P002")
    assert "Visit note (2025-12-15, intake):" in text
    # Labelled as today's assessment and plan since fix 6 (the whole box is today's plan).
    assert "Clinician's assessment and plan today (2026-01-22):\nRoutine follow-up. Stable. Discussed DSD eligibility." in text


def test_pasted_lab_text_is_labelled_with_its_date_and_source() -> None:
    text = _model_input("P005")
    assert "Pasted lab text (entered 2026-02-24, previous results):" in text


def test_labs_saved_in_the_new_shape_are_read_by_the_rules() -> None:
    p = _patient("P001")
    p["labs"] = {"creatinine": [{"date": "2025-12-01", "value": "1.4", "unit": "mg/dL", "source": "previous"}]}
    ctx = build_patient_context(p)
    assert days_since_lab(ctx, "creatinine") == 52
    assert ctx.latest_labs["creatinine"].unit == "mg/dL"


# The add-patient form: one row per result.

def test_a_creatinine_in_mg_per_dl_keeps_its_unit() -> None:
    from artemis.patient.labs import creatinine_umol_per_l, lab_rows_to_entries

    entries, errors = lab_rows_to_entries(
        [{"test": "creatinine", "date": "2025-10-01", "value": "1.4", "unit": "mg/dL"}], source="previous"
    )
    assert errors == []
    assert entries == {"creatinine": [{"date": "2025-10-01", "value": "1.4", "unit": "mg/dL", "source": "previous"}]}
    assert creatinine_umol_per_l("1.4", "mg/dL") == pytest.approx(123.8, abs=0.1)


def test_a_creatinine_with_no_unit_that_looks_like_mg_per_dl_is_refused() -> None:
    from artemis.patient.labs import lab_rows_to_entries

    entries, errors = lab_rows_to_entries(
        [{"test": "creatinine", "date": "2025-10-01", "value": "1.4", "unit": ""}], source="today"
    )
    assert entries == {}
    assert errors and "mg/dL" in errors[0]


def test_a_blank_unit_takes_the_usual_unit_and_keeps_the_value_as_typed() -> None:
    from artemis.patient.labs import lab_rows_to_entries

    entries, errors = lab_rows_to_entries(
        [{"test": "viral_load", "date": "2025-10-01", "value": "<50", "unit": ""}], source="today"
    )
    assert errors == []
    assert entries["viral_load"][0]["unit"] == "copies/mL"
    assert entries["viral_load"][0]["value"] == "<50"


def test_a_date_in_another_format_is_refused_not_stamped_with_today() -> None:
    from artemis.patient.labs import lab_rows_to_entries

    entries, errors = lab_rows_to_entries(
        [{"test": "viral_load", "date": "01/10/2025", "value": "40", "unit": "copies/mL"}], source="previous"
    )
    assert entries == {}
    assert errors and "01/10/2025" in errors[0]
