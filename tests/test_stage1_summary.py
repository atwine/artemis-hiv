from __future__ import annotations

from artemis.patient.record import build_patient_context
from artemis.patient.summary import build_stage1_summary


def test_summary_carries_the_record_and_lists_only_truly_empty_fields() -> None:
    patient = {
        "patient_id": "p123",
        "art_regimen_current": ["TDF", "3TC", "DTG"],
        "today_encounter": {
            "date": "2024-01-01",
            "note": "Check creatinine and VL next visit.",
        },
        "visits": [
            {
                "date": "2023-12-01",
                "clinician_note": "Sleep disturbance lately.\nPlan: counsel sleep hygiene.",
            }
        ],
        "labs": {
            "creatinine": [{"date": "2023-01-01", "value_umol_per_l": 80}],
            "viral_load": [{"date": "2023-11-01", "value_copies_per_ml": 200}],
        },
    }

    summary = build_stage1_summary(patient=patient, context=build_patient_context(patient))

    assert summary["patient_id"] == "p123"
    assert summary["encounter_date"] == "2024-01-01"
    assert summary["current_regimen"] == ["TDF", "3TC", "DTG"]
    # Today's whole note is the plan, with or without a "Plan:" prefix (fix 6).
    assert summary["assessment_and_plan_today"] == "Check creatinine and VL next visit."
    assert summary["latest_labs"]["viral_load"]["value"] == "200"
    assert summary["latest_labs"]["viral_load"]["unit"] == "copies/mL"
    assert summary["latest_labs"]["creatinine"]["days_before_visit"] == 365
    assert summary["not_recorded"] == [
        "regimen history",
        "other medications",
        "complaints",
        "examination findings",
        "orders today",
        "medicine changes today",
    ]
