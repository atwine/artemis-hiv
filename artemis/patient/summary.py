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


def _extract_past_complaints(patient: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Light heuristic: surface note snippets with common complaint terms.
    terms = [
        "pain",
        "sleep",
        "fever",
        "cough",
        "headache",
        "nausea",
        "vomit",
        "dizziness",
    ]
    out: List[Dict[str, Any]] = []
    for v in patient.get("visits", []) or []:
        note = (v.get("clinician_note") or "").strip()
        if not note:
            continue
        low = note.lower()
        if any(t in low for t in terms):
            out.append({"date": v.get("date"), "text": note})
    return out


def _extract_plans(patient: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Light heuristic: capture lines that look like a Plan in historical notes.
    out: List[Dict[str, Any]] = []
    for v in patient.get("visits", []) or []:
        note = (v.get("clinician_note") or "").strip()
        if not note:
            continue
        lines = [ln.strip() for ln in note.splitlines()]
        plan_lines = [ln for ln in lines if ln.lower().startswith("plan:")]
        if plan_lines:
            out.append({"date": v.get("date"), "items": plan_lines})
    return out


def _extract_today_plan(patient: Dict[str, Any]) -> List[str]:
    today = (patient.get("today_encounter", {}) or {})
    note = (today.get("note") or "").strip()
    if not note:
        return []
    lines = [ln.strip() for ln in note.splitlines()]
    return [ln for ln in lines if ln.lower().startswith("plan:")]


def build_stage1_summary(*, patient: Dict[str, Any], context: PatientContext) -> Dict[str, Any]:
    """Build a Stage‑1-style summary JSON without altering existing alert logic.

    The summary includes light heuristics and explicit missing flags where data is absent.
    """

    past_labs = _extract_past_labs(patient, context.encounter_date)
    latest_labs = _latest_labs_map(patient, context.encounter_date)
    past_complaints = _extract_past_complaints(patient)
    past_plans = _extract_plans(patient)

    # Optional/rare in current demo schema; mark as missing when not present
    regimen_history = list(patient.get("regimen_history") or [])
    non_hiv_meds = list(patient.get("non_hiv_meds") or [])

    current_regimen = list(context.art_regimen_current or [])
    today_plan = _extract_today_plan(patient)

    missing_flags = {
        "regimen_history": len(regimen_history) == 0,
        "non_hiv_meds": len(non_hiv_meds) == 0,
        "past_plans": len(past_plans) == 0,
        "past_complaints": len(past_complaints) == 0,
        "today_plan": len(today_plan) == 0,
    }

    return {
        "patient_id": context.patient_id,
        "encounter_date": _iso(context.encounter_date),
        "current_regimen": current_regimen,
        "regimen_history": regimen_history,
        "non_hiv_meds": non_hiv_meds,
        "past_labs": past_labs,
        "latest_labs": latest_labs,
        "past_complaints": past_complaints,
        "past_plans": past_plans,
        "today_plan": today_plan,
        "missing_flags": missing_flags,
    }
