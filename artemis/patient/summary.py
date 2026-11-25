from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import date

from artemis.patient.labs import LabEntry, latest_entries, read_lab_entries
from artemis.patient.record import PatientContext


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if isinstance(d, date) else None


def _lab_item(e: LabEntry, visit_date: date) -> Dict[str, Any]:
    return {
        "lab": e.test,
        "date": e.date.isoformat(),
        "value": e.value,
        "unit": e.unit,
        "days_before_visit": (visit_date - e.date).days,
        "source": e.source,
    }


def _extract_past_labs(patient: Dict[str, Any], visit_date: date) -> List[Dict[str, Any]]:
    return [_lab_item(e, visit_date) for e in read_lab_entries(patient)]


def _latest_labs_map(patient: Dict[str, Any], visit_date: date) -> Dict[str, Dict[str, Any]]:
    latest = latest_entries(read_lab_entries(patient), visit_date)
    return {test: _lab_item(e, visit_date) for test, e in latest.items()}


def build_stage1_summary(*, patient: Dict[str, Any], context: PatientContext) -> Dict[str, Any]:
    """The structured summary the AI reads: what is recorded, and which fields are truly empty.

    Nothing here is guessed. A field is listed under "not_recorded" only when the record has
    nothing in it (fix 6; the old version flagged data as missing whenever a keyword search
    found nothing, and read medicines from a key no record had).
    """

    today = patient.get("today_encounter") or {}
    fields: Dict[str, Any] = {
        "current_regimen": list(context.art_regimen_current or []),
        "regimen_history": list(patient.get("regimen_history") or []),
        "other_medications": list(context.other_medications or []),
        "complaints_today": (context.complaints_symptoms or "").strip(),
        "examination_today": (context.examination_findings or "").strip(),
        # The whole "Clinician's Assessment & Plan" box is today's plan (owner's choice, fix 6).
        "assessment_and_plan_today": (today.get("note") or "").strip(),
        "orders_today": list(today.get("orders") or []),
        "medicine_changes_today": list(today.get("med_changes") or []),
        "past_labs": _extract_past_labs(patient, context.encounter_date),
        "latest_labs": _latest_labs_map(patient, context.encounter_date),
    }
    labels = {
        "current_regimen": "current regimen",
        "regimen_history": "regimen history",
        "other_medications": "other medications",
        "complaints_today": "complaints",
        "examination_today": "examination findings",
        "assessment_and_plan_today": "assessment and plan today",
        "orders_today": "orders today",
        "medicine_changes_today": "medicine changes today",
        "past_labs": "lab results",
    }
    not_recorded = [labels[k] for k in labels if not fields[k]]
    if not fields["past_labs"] and context.labs_narrative:
        not_recorded.remove("lab results")  # results exist, but only as pasted text

    summary: Dict[str, Any] = {
        "patient_id": context.patient_id,
        "encounter_date": _iso(context.encounter_date),
    }
    summary.update(fields)
    summary["not_recorded"] = not_recorded
    return summary
