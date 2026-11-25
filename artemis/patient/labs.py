"""Lab results: one shape for every result, with its unit, date, age and source.

A patient's `labs` maps a test name to a list of results. Each result is stored as

    {"date": "YYYY-MM-DD", "value": "1.4", "unit": "mg/dL", "source": "today" | "previous"}

`value` is kept as typed ("<50" stays "<50"). Records made before fix 4 store the unit in the
key name instead (`value_umol_per_l`, `value_copies_per_ml`); those are read too. Text pasted
into the old add-case lab boxes is kept under `labs_narrative` and is never read as numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# The tests the add-case form offers, with their units. The first unit is the usual one.
TEST_UNITS: Dict[str, List[str]] = {
    "viral_load": ["copies/mL"],
    "cd4": ["cells/uL"],
    "creatinine": ["umol/L", "mg/dL"],
    "egfr": ["mL/min/1.73m2"],
    "hemoglobin": ["g/dL"],
    "alt": ["U/L"],
    "fasting_glucose": ["mmol/L", "mg/dL"],
    "hba1c": ["%"],
    "total_cholesterol": ["mmol/L", "mg/dL"],
    "ldl": ["mmol/L", "mg/dL"],
    "hdl": ["mmol/L", "mg/dL"],
    "triglycerides": ["mmol/L", "mg/dL"],
}
TEST_NAMES: Dict[str, str] = {
    "viral_load": "viral load",
    "cd4": "CD4 count",
    "creatinine": "creatinine",
    "egfr": "eGFR",
    "hemoglobin": "haemoglobin",
    "alt": "ALT",
    "fasting_glucose": "fasting glucose",
    "hba1c": "HbA1c",
    "total_cholesterol": "total cholesterol",
    "ldl": "LDL cholesterol",
    "hdl": "HDL cholesterol",
    "triglycerides": "triglycerides",
}

# Older records keep the unit in the value's key name.
_LEGACY_VALUE_KEYS: Dict[str, str] = {
    "value_umol_per_l": "umol/L",
    "value_copies_per_ml": "copies/mL",
    "value_mg_dl": "mg/dL",
    "value_mg_per_dl": "mg/dL",
}

_CREATININE_MG_DL_TO_UMOL_L = 88.4
# A creatinine below this with no unit is almost certainly mg/dL (umol/L values start near 40).
_CREATININE_UMOL_FLOOR = 20.0
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class LabEntry:
    test: str
    date: date
    value: str  # as typed, for example "<50"
    unit: str
    source: str  # "today", "previous" or "record" (older records say neither)

    @property
    def number(self) -> Optional[float]:
        return to_number(self.value)


@dataclass(frozen=True)
class LabNote:
    """Lab results pasted as free text into the old add-case boxes."""

    date: Optional[date]
    source: str
    text: str


def to_number(value: Any) -> Optional[float]:
    """The number in a lab value, or None. "<50" reads as 50: callers decide what "<" means."""
    m = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return float(m.group()) if m else None


def creatinine_umol_per_l(value: Any, unit: str) -> Optional[float]:
    number = to_number(value)
    if number is None:
        return None
    return round(number * _CREATININE_MG_DL_TO_UMOL_L, 1) if unit == "mg/dL" else number


def _parse_date(text: Any) -> Optional[date]:
    try:
        return datetime.strptime(str(text), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def read_lab_entries(patient: Dict[str, Any]) -> List[LabEntry]:
    """Every structured result in the record, oldest first. Results with no readable date are skipped."""
    out: List[LabEntry] = []
    for test, results in (patient.get("labs") or {}).items():
        if test == "labs_narrative":
            continue
        for r in results or []:
            d = _parse_date((r or {}).get("date"))
            if d is None:
                continue
            if "value" in r:
                value, unit = r.get("value"), r.get("unit") or ""
            else:
                key = next((k for k in r if k in _LEGACY_VALUE_KEYS), None)
                value = r.get(key) if key else next((v for k, v in r.items() if k not in {"date", "source"}), None)
                unit = _LEGACY_VALUE_KEYS.get(key or "", "")
            out.append(LabEntry(test=test, date=d, value=str(value), unit=unit, source=r.get("source") or "record"))
    return sorted(out, key=lambda e: (e.date, e.test))


def read_lab_notes(patient: Dict[str, Any]) -> List[LabNote]:
    notes: List[LabNote] = []
    for r in (patient.get("labs") or {}).get("labs_narrative") or []:
        if isinstance(r, dict) and (r.get("narrative_text") or "").strip():
            notes.append(LabNote(date=_parse_date(r.get("date")), source=r.get("source") or "unknown", text=r["narrative_text"].strip()))
    return notes


def latest_entries(entries: List[LabEntry], visit_date: date) -> Dict[str, LabEntry]:
    """The newest result of each test on or before the visit date."""
    latest: Dict[str, LabEntry] = {}
    for e in entries:
        if e.date <= visit_date and (e.test not in latest or e.date >= latest[e.test].date):
            latest[e.test] = e
    return latest


def describe(entry: LabEntry, visit_date: date) -> str:
    """'creatinine 76 umol/L on 2025-12-15 (38 days before the visit)'."""
    name = TEST_NAMES.get(entry.test, entry.test.replace("_", " "))
    unit = f" {entry.unit}" if entry.unit else ""
    days = (visit_date - entry.date).days
    when = f"{days} days before the visit" if days > 0 else ("on the visit date" if days == 0 else f"{-days} days after the visit")
    return f"{name} {entry.value}{unit} on {entry.date.isoformat()} ({when})"


def lab_section(patient: Dict[str, Any], visit_date: date) -> str:
    """The laboratory part of the model's input: every result, dated, then any pasted text."""
    lines = [f"- {describe(e, visit_date)}" for e in read_lab_entries(patient)]
    for n in read_lab_notes(patient):
        entered = n.date.isoformat() if n.date else "date not recorded"
        source = {"today": "today's results", "previous": "previous results"}.get(n.source, "results")
        lines.append(f"Pasted lab text (entered {entered}, {source}):\n{n.text}")
    return "\n".join(lines) if lines else "None recorded"


def lab_rows_to_entries(rows: List[Dict[str, Any]], *, source: str) -> Tuple[Dict[str, List[Dict[str, str]]], List[str]]:
    """Turn the add-case form's lab rows into stored results, or explain what's wrong.

    Nothing is saved when any row has a problem, so a half-read table never reaches the rules.
    """
    out: Dict[str, List[Dict[str, str]]] = {}
    errors: List[str] = []
    for i, row in enumerate(rows, start=1):
        test = str(row.get("test") or "").strip()
        when = str(row.get("date") or "").strip()
        value = str(row.get("value") or "").strip()
        unit = str(row.get("unit") or "").strip()
        if not (test or when or value or unit):
            continue  # an empty row the table added
        where = f"Row {i} ({TEST_NAMES.get(test, test) or 'no test'})"
        if test not in TEST_UNITS:
            errors.append(f"{where}: pick a test from the list.")
            continue
        if not _ISO_DATE.match(when) or _parse_date(when) is None:
            errors.append(f"{where}: the date '{when}' must be written YYYY-MM-DD.")
            continue
        if to_number(value) is None:
            errors.append(f"{where}: the value '{value}' has no number in it.")
            continue
        unit = unit or TEST_UNITS[test][0]
        if unit not in TEST_UNITS[test]:
            errors.append(f"{where}: '{unit}' is not a unit for this test ({', '.join(TEST_UNITS[test])}).")
            continue
        if test == "creatinine" and unit == "umol/L" and to_number(value) < _CREATININE_UMOL_FLOOR:
            errors.append(f"{where}: {value} looks like mg/dL, not umol/L. Check the unit for this creatinine.")
            continue
        out.setdefault(test, []).append({"date": when, "value": value, "unit": unit, "source": source})
    return ({} if errors else out), errors
