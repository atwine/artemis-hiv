"""A new patient case from the add-case form: one builder for the Streamlit form and the API.

Moved out of app.py (plan item 4.6's suggestion, owner 2026-11-26) so both make the same record.
The rules are the Streamlit form's, with the size limits the owner agreed for the API:
- a patient ID is required: letters, numbers, spaces and dashes, up to 40 characters (an ID
  already in use is the caller's check, since it needs the patient list);
- age 0-120 and sex M or F are optional, and a made-up name is optional;
- ART drugs come from the app's pick list (REGIMEN_CHOICES);
- complaints, examination findings and history are text, each up to 5,000 characters;
- lab results are rows read by artemis.patient.labs.lab_rows_to_entries, at most 50 in all.
Nothing is built when anything is wrong: the errors say what to fix.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from artemis.patient.labs import lab_rows_to_entries
from artemis.patient.medicines import REGIMEN_CHOICES, other_medicines, regimen_codes

MAX_TEXT = 5000
MAX_LAB_ROWS = 50
_PATIENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,39}$")
_LAB_LABELS = {"today": "Today's", "previous": "Previous"}

LabRow = Tuple[Dict[str, Any], str]  # (the form's row: test, date, value, unit), and "today" or "previous"


@dataclass(frozen=True)
class CaseForm:
    patient_id: str
    name: str = ""
    age_years: Optional[int] = None
    sex: str = ""
    art_regimen: Sequence[str] = ()  # picks from REGIMEN_CHOICES, e.g. "TLD" or "DTG"
    other_medications: Sequence[str] = ()  # one medicine per item
    complaints: str = ""
    examination_findings: str = ""
    prior_history: str = ""
    lab_rows: Sequence[LabRow] = field(default_factory=tuple)


def _form_errors(form: CaseForm) -> List[str]:
    errors: List[str] = []
    pid = (form.patient_id or "").strip()
    if not pid:
        errors.append("Patient ID is required.")
    elif not _PATIENT_ID.match(pid):
        errors.append("Patient ID: use letters, numbers, spaces and dashes only, up to 40 characters.")
    if form.age_years is not None and not 0 <= form.age_years <= 120:
        errors.append("Age must be between 0 and 120 years.")
    if (form.sex or "") not in {"", "M", "F"}:
        errors.append("Sex must be M or F, or left blank.")
    unknown = [d for d in form.art_regimen if d not in REGIMEN_CHOICES]
    if unknown:
        errors.append(f"ART regimen: pick from the list ({', '.join(unknown)} is not on it).")
    for label, text in (("Name", form.name), ("Complaints & Symptoms", form.complaints),
                        ("Examination Findings", form.examination_findings), ("Prior history", form.prior_history)):
        if len(text or "") > MAX_TEXT:
            errors.append(f"{label}: at most 5,000 characters.")
    if len(form.lab_rows) > MAX_LAB_ROWS:
        errors.append(f"At most {MAX_LAB_ROWS} lab results per case.")
    return errors


def _labs(rows: Sequence[LabRow]) -> Tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    labs: Dict[str, List[Dict[str, str]]] = {}
    errors: List[str] = []
    for source in ("today", "previous"):
        entries, problems = lab_rows_to_entries([r for r, s in rows if s == source], source=source)
        errors += [f"{_LAB_LABELS[source]} lab results, {e}" for e in problems]
        for test, results in entries.items():
            labs.setdefault(test, []).extend(results)
    return labs, errors


def build_case_record(form: CaseForm, *, today: datetime.date) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """The patient record to save, or (None, the reasons it can't be built)."""
    errors = _form_errors(form)
    labs, lab_errors = _labs(form.lab_rows) if len(form.lab_rows) <= MAX_LAB_ROWS else ({}, [])
    errors += lab_errors
    if errors:
        return None, errors

    encounter = today.isoformat()
    record: Dict[str, Any] = {"patient_id": form.patient_id.strip()}
    if (form.name or "").strip():
        record["name"] = form.name.strip()
    record.update({
        "age_years": form.age_years,
        "sex": form.sex or None,  # as the Streamlit form has always saved it
        "art_regimen_current": regimen_codes(list(form.art_regimen)),  # TLD becomes TDF, 3TC, DTG
        "other_medications": other_medicines(list(form.other_medications)),
        "visits": [],
        "labs": labs,
        "today_encounter": {"date": encounter, "note": "", "orders": [], "med_changes": []},
        "intake": {
            "complaints_symptoms": form.complaints or "",
            "examination_findings": form.examination_findings or "",
            "prior_history": form.prior_history or "",
        },
    })
    # The intake as one dated note too, the shape the rules, the search and the AI read.
    parts = [
        f"{heading}:\n{text}"
        for heading, text in (
            ("Complaints & Symptoms", record["intake"]["complaints_symptoms"]),
            ("Examination Findings", record["intake"]["examination_findings"]),
            ("Significant history prior to today's visit", record["intake"]["prior_history"]),
        )
        if text
    ]
    if parts:
        record["visits"].append({"date": encounter, "type": "intake", "clinician_note": "\n\n".join(parts)})
    return record, []
