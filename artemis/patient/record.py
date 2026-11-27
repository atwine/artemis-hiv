"""Patient parsing utilities.

This module normalizes structured + unstructured patient data into a format
that deterministic alert rules can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from artemis.patient.labs import lab_section, latest_entries, read_lab_entries
from artemis.patient.medicines import other_medicines, regimen_codes


def _parse_iso_date(value: str) -> date:
    # Rationale: mock patient data uses ISO dates (YYYY-MM-DD). We normalize to `date`
    # for consistent comparisons.
    return datetime.strptime(value, "%Y-%m-%d").date()


def _days_between(d1: date, d2: date) -> int:
    return abs((d2 - d1).days)


@dataclass(frozen=True)
class LabResult:
    name: str
    date: date
    value: Any
    unit: str = ""


@dataclass(frozen=True)
class PatientContext:
    patient_id: str
    encounter_date: date
    art_regimen_current: List[str]
    notes_text: str
    latest_labs: Dict[str, LabResult]
    # NEW: Structured access to intake fields (optional, backward compatible)
    other_medications: List[str] = field(default_factory=list)
    complaints_symptoms: str = ""
    examination_findings: str = ""
    # NEW: Additional patient demographics and lab narrative
    age_years: Optional[int] = None
    sex: str = ""
    labs_narrative: str = ""
    # What the model reads: every lab result dated with its age and unit (fix 4), and the
    # notes oldest first, each labelled with its date, with today's note marked as today's.
    lab_section: str = "None recorded"
    art_regimen_as_entered: str = ""
    dated_notes: str = ""


def build_patient_context(patient: Dict[str, Any]) -> PatientContext:
    """Build a normalized patient context.

    The context includes:
    - encounter date (today)
    - current ART regimen
    - concatenated notes text (history + today)
    - latest lab values by lab name
    - structured intake fields (optional, for new patient records)
    """

    encounter_date = _parse_iso_date(patient["today_encounter"]["date"])

    # The antiretroviral codes, however the regimen was written (fix 5), plus the text as entered.
    regimen_as_entered = patient.get("art_regimen_as_entered") or ", ".join(
        s.strip() for s in patient.get("art_regimen_current") or [] if s and s.strip()
    )
    art_regimen_current = regimen_codes(patient.get("art_regimen_current") or [])

    notes_parts: List[str] = []
    for v in patient.get("visits", []) or []:
        note = (v.get("clinician_note") or "").strip()
        if note:
            notes_parts.append(note)

    today_note = (patient.get("today_encounter", {}).get("note") or "").strip()
    if today_note:
        notes_parts.append(today_note)

    notes_text = "\n".join(notes_parts)

    # The newest result of each test on or before the visit, whatever shape it was saved in.
    latest_labs: Dict[str, LabResult] = {
        test: LabResult(name=test, date=e.date, value=e.value, unit=e.unit)
        for test, e in latest_entries(read_lab_entries(patient), encounter_date).items()
    }

    # NEW: Extract structured fields if available (backward compatible)
    other_meds = other_medicines(patient.get("other_medications") or [])
    intake = patient.get("intake") or {}
    complaints = intake.get("complaints_symptoms", "")
    exam_findings = intake.get("examination_findings", "")
    
    # Extract age and sex
    age_years = patient.get("age_years")
    sex = patient.get("sex", "")
    
    # Extract lab narrative text
    labs_narrative_parts: List[str] = []
    labs_raw = patient.get("labs") or {}
    if "labs_narrative" in labs_raw:
        for entry in labs_raw.get("labs_narrative", []):
            if isinstance(entry, dict):
                narrative = entry.get("narrative_text", "")
                if narrative:
                    labs_narrative_parts.append(narrative)
    labs_narrative = "\n\n".join(labs_narrative_parts)

    dated_parts: List[str] = []
    for v in patient.get("visits", []) or []:
        note = (v.get("clinician_note") or "").strip()
        if note:
            label = ", ".join(x for x in (v.get("date"), v.get("type")) if x) or "date not recorded"
            dated_parts.append(f"Visit note ({label}):\n{note}")
    dated_parts.append(
        f"Clinician's assessment and plan today ({encounter_date.isoformat()}):\n{today_note or 'none written'}"
    )

    return PatientContext(
        patient_id=str(patient.get("patient_id")),
        encounter_date=encounter_date,
        art_regimen_current=art_regimen_current,
        notes_text=notes_text,
        latest_labs=latest_labs,
        other_medications=other_meds,
        complaints_symptoms=complaints,
        examination_findings=exam_findings,
        age_years=age_years,
        sex=sex,
        labs_narrative=labs_narrative,
        lab_section=lab_section(patient, encounter_date),
        art_regimen_as_entered=regimen_as_entered,
        dated_notes="\n\n".join(dated_parts),
    )


def days_since_lab(patient_context: PatientContext, lab_name: str) -> Optional[int]:
    """Return number of days since the latest lab, or None if missing."""

    lab = patient_context.latest_labs.get(lab_name)
    if lab is None:
        return None

    return _days_between(lab.date, patient_context.encounter_date)
