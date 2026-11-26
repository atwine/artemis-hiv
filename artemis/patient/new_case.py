"""A new patient case from the add-case form: one builder for the Streamlit form and the API.

Moved out of app.py (plan item 4.6's suggestion, owner 2026-11-26) so both make the same record.
The rules are the Streamlit form's, with the size limits the owner agreed for the API:
- a patient ID is required: letters, numbers, spaces and dashes, up to 40 characters (an ID
  already in use is the caller's check, since it needs the patient list);
- age 0-120 and sex M or F are optional, and a made-up name is optional;
- ART drugs come from the app's pick list (REGIMEN_CHOICES);
- complaints, examination findings and history are text, each up to 5,000 characters, and each
  other-medicine line up to 200;
- lab results are rows read by artemis.patient.labs.lab_rows_to_entries, at most 50 in all;
- the visit date (today when not given), a visit type from VISIT_TYPES, and today's clinical
  note up to 20,000 characters (the visit check's own limit) make today's visit;
- previous ART: up to 20 regimens from the pick list, each with a start and an end date, ending
  by the visit date; saved oldest first as the record's regimen history, in drug codes.
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
MAX_MEDICINE = 200  # characters in one medicine line
MAX_NOTE = 20000  # the visit check's note limit
MAX_PREVIOUS_ART = 20
# The visit types the form offers (owner, 2026-11-26: "A, four choices"; the doctor may add
# "Drug refill only" in Phase 7).
VISIT_TYPES = ("Routine review", "First visit", "Unscheduled visit", "Results review")
_PATIENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,39}$")
_LAB_LABELS = {"today": "Today's", "previous": "Previous"}

LabRow = Tuple[Dict[str, Any], str]  # (the form's row: test, date, value, unit), and "today" or "previous"


@dataclass(frozen=True)
class PreviousArt:
    regimen: Sequence[str]  # picks from REGIMEN_CHOICES
    start_date: datetime.date
    end_date: datetime.date


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
    visit_date: Optional[datetime.date] = None  # today when not given
    visit_type: str = ""  # one of VISIT_TYPES, or blank
    previous_art: Sequence[PreviousArt] = ()
    todays_note: str = ""


PREVIOUS_ART_COLUMNS = ["drugs", "start_date", "end_date"]
_CHOICE_BY_LOWER = {c.lower(): c for c in REGIMEN_CHOICES}


def previous_art_from_rows(rows: Sequence[Dict[str, str]]) -> Tuple[List[PreviousArt], List[str]]:
    """The Streamlit form's previous-ART table (text cells) as PreviousArt rows, or what's wrong.

    Drugs are picks from the list separated by commas ("TLE", or "AZT, 3TC, NVP"), matched
    whatever their case; a name not on the list is kept, for build_case_record to explain.
    A row left fully blank is skipped (the table's empty last row)."""
    art: List[PreviousArt] = []
    errors: List[str] = []
    for n, row in enumerate(rows, start=1):
        cells = {c: (row.get(c) or "").strip() for c in PREVIOUS_ART_COLUMNS}
        if not any(cells.values()):
            continue
        where = f"Previous ART, row {n}"
        drugs = [d.strip() for d in cells["drugs"].split(",") if d.strip()]
        if not drugs:
            errors.append(f"{where}: pick at least one drug.")
        if not (cells["start_date"] and cells["end_date"]):
            errors.append(f"{where}: give a start and an end date.")
            continue
        try:
            start, end = (datetime.date.fromisoformat(cells[c]) for c in ("start_date", "end_date"))
        except ValueError:
            errors.append(f"{where}: dates must be YYYY-MM-DD.")
            continue
        if drugs:
            art.append(PreviousArt(regimen=[_CHOICE_BY_LOWER.get(d.lower(), d) for d in drugs], start_date=start, end_date=end))
    return ([], errors) if errors else (art, [])


def _previous_art_errors(form: CaseForm, visit_date: datetime.date) -> List[str]:
    if len(form.previous_art) > MAX_PREVIOUS_ART:
        return [f"Previous ART: at most {MAX_PREVIOUS_ART} regimens."]
    errors: List[str] = []
    for n, art in enumerate(form.previous_art, start=1):
        where = f"Previous ART, row {n}"
        unknown = [d for d in art.regimen if d not in REGIMEN_CHOICES]
        if not art.regimen:
            errors.append(f"{where}: pick at least one drug.")
        elif unknown:
            errors.append(f"{where}: pick from the list ({', '.join(unknown)} is not on it).")
        if art.end_date < art.start_date:
            errors.append(f"{where}: it ends before it starts.")
        elif art.end_date > visit_date:
            errors.append(f"{where}: it ends after the visit date.")
    return errors


def _form_errors(form: CaseForm, visit_date: datetime.date) -> List[str]:
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
    if any(len(m) > MAX_MEDICINE for m in form.other_medications):
        errors.append(f"Other medications: each at most {MAX_MEDICINE} characters.")
    if len(form.lab_rows) > MAX_LAB_ROWS:
        errors.append(f"At most {MAX_LAB_ROWS} lab results per case.")
    if (form.visit_type or "") not in {"", *VISIT_TYPES}:
        errors.append(f"Visit type: pick from the list ({', '.join(VISIT_TYPES)}).")
    if len(form.todays_note or "") > MAX_NOTE:
        errors.append("Today's clinical note: at most 20,000 characters.")
    return errors + _previous_art_errors(form, visit_date)


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
    visit_date = form.visit_date or today
    errors = _form_errors(form, visit_date)
    labs, lab_errors = _labs(form.lab_rows) if len(form.lab_rows) <= MAX_LAB_ROWS else ({}, [])
    errors += lab_errors
    if errors:
        return None, errors

    encounter = visit_date.isoformat()
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
        "today_encounter": {"date": encounter, "note": form.todays_note or "", "orders": [], "med_changes": []},
        "intake": {
            "complaints_symptoms": form.complaints or "",
            "examination_findings": form.examination_findings or "",
            "prior_history": form.prior_history or "",
        },
    })
    if form.visit_type:
        record["today_encounter"]["visit_type"] = form.visit_type
    if form.previous_art:
        record["regimen_history"] = [
            {"start_date": a.start_date.isoformat(), "end_date": a.end_date.isoformat(), "regimen": regimen_codes(list(a.regimen))}
            for a in sorted(form.previous_art, key=lambda a: a.start_date)
        ]
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
