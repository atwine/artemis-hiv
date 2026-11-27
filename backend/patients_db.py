"""Patients in the database (plan 4C.2, owner 2026-11-27): the made-up patients as tables.

One patient record (the shape the rules, the search and the AI read; artemis/patient/record.py)
is stored as rows in seven tables, and read back into the same shape:
- patient: who they are, the intake text, and where the record came from ("seed" or "added");
- patient_medicine: the current ART drugs and other medicines, as written, in order;
- art_history: earlier regimens with their start and end dates;
- lab_result: each structured result, its value as typed and its unit (older records that kept
  the unit in the key's name are read once, by artemis.patient.labs.read_lab_entries);
- lab_note: lab text pasted into the old add-case boxes, never read as numbers;
- clinical_note: earlier dated notes (the intake note, past visits);
- encounter: today's visit: its date, type, note, orders and medicine changes.

Rows are only ever added: nothing here edits or deletes a patient (ACCESS.md). A field the tables
have no place for is refused, never dropped, except the demo answer key (expected_demo_outcome),
which stays with the evaluation (owner, 2026-11-27).
"""

from __future__ import annotations

import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from sqlalchemy import JSON, Column, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, Session, SQLModel, func, select

from artemis.patient.labs import LEGACY_VALUE_KEYS, read_lab_entries

Json = JSON().with_variant(JSONB(), "postgresql")
ANSWER_KEY = "expected_demo_outcome"
_PLACED = {
    "patient_id", "name", "sex", "age_years", "art_regimen_current", "art_regimen_as_entered", "other_medications",
    "regimen_history", "intake", "visits", "labs", "today_encounter",
}
_ENCOUNTER_FIELDS = {"date", "note", "orders", "med_changes", "visit_type"}
_INTAKE_FIELDS = {"complaints_symptoms", "examination_findings", "prior_history"}
# The keys each listed item may have; anything else would be lost.
_ITEM_FIELDS = {
    "regimen_history": {"start_date", "end_date", "regimen"},
    "visits": {"date", "type", "clinician_note"},
}
_LAB_NOTE_FIELDS = {"date", "source", "narrative_text"}


class UnplacedField(ValueError):
    """A record holds something the tables have no place for; loading it would lose it."""


class PatientExists(ValueError):
    """A patient with this id is already in the database."""


class Patient(SQLModel, table=True):
    __tablename__ = "patient"

    patient_id: str = Field(primary_key=True, max_length=200)
    position: int = Field(index=True, unique=True)  # the order patients are listed in
    name: Optional[str] = Field(default=None, sa_column=Column(Text))
    sex: Optional[str] = Field(default=None, max_length=16)
    age_years: Optional[int] = None
    art_regimen_as_entered: Optional[str] = Field(default=None, sa_column=Column(Text))
    complaints_symptoms: str = Field(default="", sa_column=Column(Text, nullable=False))
    examination_findings: str = Field(default="", sa_column=Column(Text, nullable=False))
    prior_history: str = Field(default="", sa_column=Column(Text, nullable=False))
    origin: str = Field(max_length=16)  # "seed" (loaded from Data/) or "added" (through the API)
    added_at: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class PatientMedicine(SQLModel, table=True):
    __tablename__ = "patient_medicine"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    kind: str = Field(max_length=8)  # "art" (current ART) or "other"
    position: int
    name: str = Field(sa_column=Column(Text, nullable=False))  # as written, e.g. "TDF" or "Amlodipine 5 mg daily"


class ArtHistory(SQLModel, table=True):
    __tablename__ = "art_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    position: int
    start_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date))
    end_date: Optional[datetime.date] = Field(default=None, sa_column=Column(Date))  # none while current
    regimen: List[str] = Field(sa_column=Column(Json, nullable=False))  # drug codes


class LabResult(SQLModel, table=True):
    __tablename__ = "lab_result"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    position: int
    test: str = Field(max_length=40)
    date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    value: str = Field(max_length=40)  # as typed, e.g. "<50"
    unit: str = Field(max_length=20)
    source: str = Field(max_length=16)  # "today", "previous" or "record" (older records say neither)


class LabNote(SQLModel, table=True):
    __tablename__ = "lab_note"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    position: int
    date: Optional[str] = Field(default=None, max_length=40)  # as written
    source: Optional[str] = Field(default=None, max_length=16)
    text: str = Field(sa_column=Column(Text, nullable=False))


class ClinicalNote(SQLModel, table=True):
    __tablename__ = "clinical_note"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    position: int
    date: Optional[str] = Field(default=None, max_length=40)  # as written, normally YYYY-MM-DD
    type: Optional[str] = Field(default=None, max_length=40)  # e.g. "intake"
    text: str = Field(sa_column=Column(Text, nullable=False))


class Encounter(SQLModel, table=True):
    __tablename__ = "encounter"

    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    date: datetime.date = Field(sa_column=Column(Date, nullable=False))
    visit_type: Optional[str] = Field(default=None, max_length=40)
    note: str = Field(default="", sa_column=Column(Text, nullable=False))
    orders: List[Any] = Field(default=[], sa_column=Column(Json, nullable=False))
    med_changes: List[Any] = Field(default=[], sa_column=Column(Json, nullable=False))


TABLES = (Patient, PatientMedicine, ArtHistory, LabResult, LabNote, ClinicalNote, Encounter)


def _date(text: Any) -> Optional[datetime.date]:
    return datetime.date.fromisoformat(text) if text else None


def _check_placed(record: Dict[str, Any]) -> None:
    pid = record.get("patient_id")
    unplaced = sorted(set(record) - _PLACED - {ANSWER_KEY})
    unplaced += [f"today_encounter.{k}" for k in sorted(set(record.get("today_encounter") or {}) - _ENCOUNTER_FIELDS)]
    unplaced += [f"intake.{k}" for k in sorted(set(record.get("intake") or {}) - _INTAKE_FIELDS)]
    for name, allowed in _ITEM_FIELDS.items():
        unplaced += [f"{name}.{k}" for item in record.get(name) or [] for k in sorted(set(item) - allowed)]
    notes = (record.get("labs") or {}).get("labs_narrative") or []
    unplaced += [f"labs.labs_narrative.{k}" for n in notes for k in sorted(set(n) - _LAB_NOTE_FIELDS)]
    readable = {(e.test, e.date.isoformat()) for e in read_lab_entries(record)}
    for test, results in (record.get("labs") or {}).items():
        if test == "labs_narrative":
            continue
        for r in results or []:
            r = r or {}
            if (test, str(r.get("date"))) not in readable:
                unplaced.append(f"labs.{test} (a result with no readable date)")
            # One value per result: "value" (with its unit), or one older key that names the unit.
            values = [k for k in r if k == "value" or k in LEGACY_VALUE_KEYS]
            extra = sorted(set(r) - {"date", "unit", "source"} - set(values[:1]))
            unplaced += [f"labs.{test}.{k}" for k in extra]
    for field in ("complaints_symptoms", "examination_findings", "prior_history"):
        if field in (record.get("intake") or {}) and not isinstance(record["intake"][field], str):
            unplaced.append(f"intake.{field} (not text)")
    for field in ("art_regimen_current", "other_medications"):
        unplaced += [f"{field} (not text)" for m in record.get(field) or [] if not isinstance(m, str)]
    if unplaced:
        raise UnplacedField(f"{pid}: no place for {', '.join(unplaced)}")


def rows_for(record: Dict[str, Any], *, position: int, origin: str, added_at: datetime.datetime) -> List[SQLModel]:
    """The rows that hold one patient record. Raises UnplacedField rather than lose anything."""
    _check_placed(record)
    pid = str(record["patient_id"])
    intake = record.get("intake") or {}
    rows: List[SQLModel] = [Patient(
        patient_id=pid, position=position, name=record.get("name"), sex=record.get("sex"),
        age_years=record.get("age_years"), art_regimen_as_entered=record.get("art_regimen_as_entered"),
        complaints_symptoms=intake.get("complaints_symptoms", ""), examination_findings=intake.get("examination_findings", ""),
        prior_history=intake.get("prior_history", ""), origin=origin, added_at=added_at,
    )]
    for kind, names in (("art", record.get("art_regimen_current") or []), ("other", record.get("other_medications") or [])):
        rows += [PatientMedicine(patient_id=pid, kind=kind, position=n, name=name) for n, name in enumerate(names)]
    rows += [
        ArtHistory(patient_id=pid, position=n, start_date=_date(h.get("start_date")), end_date=_date(h.get("end_date")),
                   regimen=list(h.get("regimen") or []))
        for n, h in enumerate(record.get("regimen_history") or [])
    ]
    rows += [
        LabResult(patient_id=pid, position=n, test=e.test, date=e.date, value=e.value, unit=e.unit, source=e.source)
        for n, e in enumerate(_lab_entries_in_record_order(record))
    ]
    rows += [
        LabNote(patient_id=pid, position=n, date=r.get("date"), source=r.get("source"), text=r.get("narrative_text") or "")
        for n, r in enumerate((record.get("labs") or {}).get("labs_narrative") or [])
    ]
    rows += [
        ClinicalNote(patient_id=pid, position=n, date=v.get("date"), type=v.get("type"), text=v.get("clinician_note") or "")
        for n, v in enumerate(record.get("visits") or [])
    ]
    enc = record["today_encounter"]
    rows.append(Encounter(patient_id=pid, date=_date(enc["date"]), visit_type=enc.get("visit_type"), note=enc.get("note") or "",
                          orders=list(enc.get("orders") or []), med_changes=list(enc.get("med_changes") or [])))
    return rows


def _save(session: Session, rows: List[SQLModel]) -> None:
    """The patient row first, then the rows that point to it: the tables have no relationship the
    database layer could order them by, and Postgres checks each link as the row goes in."""
    session.add(rows[0])
    session.flush()
    session.add_all(rows[1:])
    session.flush()


def _lab_entries_in_record_order(record: Dict[str, Any]):
    """Each structured result once, in the order the record lists them (test by test)."""
    for test, results in (record.get("labs") or {}).items():
        if test != "labs_narrative":
            yield from read_lab_entries({"labs": {test: results}})


def _record(p: Patient, by_kind: Dict[type, List[Any]]) -> Dict[str, Any]:
    """One patient's rows as the record shape the rules, the search and the AI read."""
    mine = {t: sorted((r for r in by_kind.get(t, []) if r.patient_id == p.patient_id), key=lambda r: getattr(r, "position", 0))
            for t in (PatientMedicine, ArtHistory, LabResult, LabNote, ClinicalNote)}
    enc = max((e for e in by_kind.get(Encounter, []) if e.patient_id == p.patient_id), key=lambda e: e.id)
    record: Dict[str, Any] = {"patient_id": p.patient_id}
    if p.name is not None:
        record["name"] = p.name
    labs: Dict[str, List[Dict[str, Any]]] = {}
    for r in mine[LabResult]:
        labs.setdefault(r.test, []).append({"date": r.date.isoformat(), "value": r.value, "unit": r.unit, "source": r.source})
    if mine[LabNote]:
        labs["labs_narrative"] = [
            {k: v for k, v in (("date", n.date), ("source", n.source), ("narrative_text", n.text)) if v is not None}
            for n in mine[LabNote]
        ]
    today: Dict[str, Any] = {"date": enc.date.isoformat(), "note": enc.note, "orders": list(enc.orders),
                             "med_changes": list(enc.med_changes)}
    if enc.visit_type:
        today["visit_type"] = enc.visit_type
    record.update({
        "sex": p.sex,
        "age_years": p.age_years,
        "art_regimen_current": [m.name for m in mine[PatientMedicine] if m.kind == "art"],
        "other_medications": [m.name for m in mine[PatientMedicine] if m.kind == "other"],
        "regimen_history": [
            {"start_date": h.start_date.isoformat() if h.start_date else None,
             "end_date": h.end_date.isoformat() if h.end_date else None, "regimen": list(h.regimen)}
            for h in mine[ArtHistory]
        ],
        "intake": {"complaints_symptoms": p.complaints_symptoms, "examination_findings": p.examination_findings,
                   "prior_history": p.prior_history},
        "visits": [{k: v for k, v in (("date", n.date), ("type", n.type), ("clinician_note", n.text)) if v is not None}
                   for n in mine[ClinicalNote]],
        "labs": labs,
        "today_encounter": today,
    })
    if p.art_regimen_as_entered is not None:
        record["art_regimen_as_entered"] = p.art_regimen_as_entered
    return record


def load_all(session: Session) -> List[Dict[str, Any]]:
    """Every patient, in the order they were loaded or added."""
    patients = session.exec(select(Patient).order_by(Patient.position)).all()
    by_kind = {t: list(session.exec(select(t)).all()) for t in TABLES[1:]}
    return [_record(p, by_kind) for p in patients]


def _next_position(session: Session) -> int:
    return (session.exec(select(func.max(Patient.position))).one() or 0) + 1


def import_records(session: Session, records: Iterable[Dict[str, Any]], *, origin: str) -> int:
    """Load records whose id the database doesn't have yet, in one save. Safe to run again: an id
    already there is skipped. Returns how many were added."""
    have = set(session.exec(select(Patient.patient_id)).all())
    position, now = _next_position(session), datetime.datetime.now(datetime.timezone.utc)
    added = 0
    for record in records:
        pid = str(record["patient_id"])
        if pid in have:
            continue
        _save(session, rows_for(record, position=position, origin=origin, added_at=now))
        have.add(pid)
        position += 1
        added += 1
    session.commit()
    return added


def add(engine: Engine, record: Dict[str, Any],
        also: Optional[Callable[[Session], List[SQLModel]]] = None) -> None:
    """Add one new case, all its rows in one save, with the rows `also` gives (its booking on the
    clinic day, plan 4C.3). An id already in use raises PatientExists and saves nothing; so does a
    second add of the same new id racing this one (the id is the key). If anything fails, nothing
    of the case is saved."""
    pid = str(record["patient_id"])
    for attempt in range(3):
        with Session(engine) as session:
            if session.get(Patient, pid) is not None:
                raise PatientExists(pid)
            try:
                _save(session, rows_for(record, position=_next_position(session), origin="added",
                                        added_at=datetime.datetime.now(datetime.timezone.utc)))
                for row in also(session) if also else []:  # a new clinic day comes before its appointment
                    session.add(row)
                    session.flush()
                session.commit()
                return
            except IntegrityError:
                session.rollback()
                if session.get(Patient, pid) is not None:
                    raise PatientExists(pid) from None
                if attempt == 2:
                    raise
                # Another new case took the same list position, or opened the same clinic day, at
                # the same moment: try again.
