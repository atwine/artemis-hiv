"""The clinic day in the database (plan 4C.3, owner 2026-11-27: "A, its visit date").

Two tables:
- clinic_day: one row per date, with its clinic, room and clinician;
- appointment: a patient booked at a time on a clinic day.

An appointment is made only by adding a case, in the same save (backend/patients_db.py add): at the
time given, on the case's visit date. A date with no clinic day gets one then, with the demo day's
clinic, room and clinician. Nothing here moves, cancels or deletes an appointment, or changes a
day (ACCESS.md). The demo day is loaded once from the seed, like the patients.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy import Column, Date, DateTime, Text, UniqueConstraint
from sqlmodel import Field, Session, SQLModel, select

from backend.models import ClinicDaySchedule


class BadSchedule(ValueError):
    """A schedule that can't be loaded: unreadable, or booking a patient with no record."""


class NoClinic(ValueError):
    """There is no clinic day yet to copy a new day's clinic, room and clinician from."""


class ClinicDayRow(SQLModel, table=True):
    __tablename__ = "clinic_day"

    date: datetime.date = Field(sa_column=Column(Date, primary_key=True))
    clinic: str = Field(sa_column=Column(Text, nullable=False))
    room: str = Field(sa_column=Column(Text, nullable=False))
    clinician: str = Field(sa_column=Column(Text, nullable=False))
    origin: str = Field(max_length=16)  # "seed" (the demo day) or "added" (opened by booking a case)


class AppointmentRow(SQLModel, table=True):
    __tablename__ = "appointment"
    # A patient is booked at most once on a day (a backup loaded twice can't book them again).
    __table_args__ = (UniqueConstraint("date", "patient_id", name="uq_appointment_day_patient"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime.date = Field(foreign_key="clinic_day.date", index=True)
    time: str = Field(max_length=5)  # HH:MM, the clinic's local time
    patient_id: str = Field(foreign_key="patient.patient_id", index=True, max_length=200)
    name: Optional[str] = Field(default=None, sa_column=Column(Text))  # shown only when the record has none
    origin: str = Field(max_length=16)
    booked_at: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


TABLES = (ClinicDayRow, AppointmentRow)


def day_on(session: Session, date: datetime.date) -> Optional[Tuple[ClinicDayRow, List[AppointmentRow]]]:
    """A clinic day and its appointments in time order (ties in the order they were booked)."""
    day = session.get(ClinicDayRow, date)
    if day is None:
        return None
    appointments = session.exec(
        select(AppointmentRow).where(AppointmentRow.date == date).order_by(AppointmentRow.time, AppointmentRow.id)
    ).all()
    return day, list(appointments)


def board_date(session: Session, today: datetime.date) -> Optional[datetime.date]:
    """The day the board shows: today's clinic day, else the most recent earlier one."""
    return session.exec(select(ClinicDayRow.date).where(ClinicDayRow.date <= today).order_by(ClinicDayRow.date.desc())).first()


def neighbours(session: Session, date: datetime.date) -> Tuple[Optional[datetime.date], Optional[datetime.date]]:
    """The clinic days just before and just after `date`, so the board can step between days."""
    before = session.exec(select(ClinicDayRow.date).where(ClinicDayRow.date < date).order_by(ClinicDayRow.date.desc())).first()
    after = session.exec(select(ClinicDayRow.date).where(ClinicDayRow.date > date).order_by(ClinicDayRow.date)).first()
    return before, after


def booking_rows(session: Session, *, patient_id: str, date: datetime.date, time: str,
                 now: datetime.datetime) -> List[SQLModel]:
    """The rows that book a new case: its appointment, and its clinic day when the date has none,
    with the clinic, room and clinician of the demo day (the first day loaded from the seed)."""
    rows: List[SQLModel] = []
    if session.get(ClinicDayRow, date) is None:
        template = session.exec(select(ClinicDayRow).order_by(ClinicDayRow.origin != "seed", ClinicDayRow.date)).first()
        if template is None:
            raise NoClinic("no clinic day to copy the clinic, room and clinician from")
        rows.append(ClinicDayRow(date=date, clinic=template.clinic, room=template.room, clinician=template.clinician,
                              origin="added"))
    rows.append(AppointmentRow(date=date, time=time, patient_id=patient_id, origin="added", booked_at=now))
    return rows


def import_schedule(session: Session, schedule: Dict[str, Any], *, origin: str) -> int:
    """Load a day's schedule (the demo day) if its date has no clinic day yet, in one save. Safe to
    run again. Returns how many appointments were added. Every booked patient must have a record."""
    from backend.patients_db import Patient

    try:
        day = ClinicDaySchedule.model_validate(schedule)
    except ValidationError as exc:
        raise BadSchedule(f"the schedule can't be read ({exc.error_count()} problems)") from exc
    if session.get(ClinicDayRow, day.date) is not None:
        return 0
    missing = sorted({b.patient_id for b in day.appointments} - set(session.exec(select(Patient.patient_id)).all()))
    if missing:
        raise BadSchedule(f"bookings for patients with no record: {', '.join(missing)}")
    now = datetime.datetime.now(datetime.timezone.utc)
    session.add(ClinicDayRow(date=day.date, clinic=day.clinic, room=day.room, clinician=day.clinician, origin=origin))
    session.flush()
    session.add_all(AppointmentRow(date=day.date, time=b.time, patient_id=b.patient_id, name=b.name, origin=origin,
                                booked_at=now) for b in day.appointments)
    session.commit()
    return len(day.appointments)
