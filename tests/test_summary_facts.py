"""Fix 6: the summary the AI reads says what is recorded, and calls nothing missing that exists."""

from __future__ import annotations

import copy

from artemis.patient.record import build_patient_context
from artemis.patient.summary import build_stage1_summary
from tests import pipeline_harness as h
from tests.test_lab_input import _model_input


def _patient(pid: str) -> dict:
    return copy.deepcopy(next(p for p in h.patients() if p["patient_id"] == pid))


def _summary(p: dict) -> dict:
    return build_stage1_summary(patient=p, context=build_patient_context(p))


def test_other_medicines_on_the_record_reach_the_summary() -> None:
    p = _patient("P001")
    p["other_medications"] = ["Metformin 500 mg twice daily"]
    s = _summary(p)
    assert s["other_medications"] == ["Metformin 500 mg twice daily"]
    assert "other medications" not in s["not_recorded"]


def test_the_whole_assessment_and_plan_box_is_todays_plan() -> None:
    s = _summary(_patient("P002"))
    assert s["assessment_and_plan_today"] == "Routine follow-up. Stable. Discussed DSD eligibility."
    assert "assessment and plan today" not in s["not_recorded"]


def test_not_recorded_lists_only_fields_that_are_truly_empty() -> None:
    assert _summary(_patient("P002"))["not_recorded"] == [
        "other medications",
        "orders today",
        "medicine changes today",
    ]
    p5 = _summary(_patient("P005"))
    assert "assessment and plan today" in p5["not_recorded"]  # P005's note today is empty
    assert "complaints" not in p5["not_recorded"]


def test_complaints_and_examination_findings_are_in_the_summary() -> None:
    s = _summary(_patient("Kintu-Test 001"))
    assert "BP 138/88 mmHg" in s["examination_today"]
    assert "gained 'a lot of weight'" in s["complaints_today"]


def test_the_model_reads_todays_assessment_and_plan_under_that_name() -> None:
    text = _model_input("P002")
    assert "Clinician's assessment and plan today (2026-01-22):\nRoutine follow-up. Stable. Discussed DSD eligibility." in text
    assert "missing_flags" not in text
