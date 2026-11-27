"""The clinic day in the database (plan 4C.3, owner 2026-11-27: "A, its visit date").

The demo day and its appointments are tables; adding a case books its appointment at a given time
on its visit date, in the same save, opening that date's clinic day (with the demo day's clinic,
room and clinician) when there is none; the board shows today's day, else the most recent earlier
one, and takes a chosen date. The tests' "today" is 2026-11-27 (tests/conftest.py), the day after
the demo day.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest
from sqlmodel import Session

from backend import clinic_db

LOCAL = {"Origin": "http://localhost:3000"}
BEFORE = json.loads((Path(__file__).parent / "fixtures" / "clinic_day_board.json").read_text(encoding="utf-8"))


def _board(api, date=None):
    return api.client.get("/api/clinic-day", params={"date": date} if date else None, headers=LOCAL)


def _add(api, **body):
    body = {"patient_id": "P100", "art_regimen": ["TLD"], "appointment_time": "11:30", **body}
    return api.client.post("/api/patients", json=body, headers=LOCAL)


def test_the_demo_day_from_the_database_is_the_board_it_was():
    """The board the file gave before the move (captured 2026-11-27), from the database now."""
    from tests.conftest import Api

    api = Api()
    with api.client:
        r = _board(api)
    assert r.status_code == 200, r.text
    # The same board, plus the two links to the days around it (none: it is the only day).
    assert r.json() == {**BEFORE, "previous_date": None, "next_date": None}


def test_with_no_clinic_day_today_the_board_shows_the_most_recent_earlier_one(api):
    assert _board(api).json()["date"] == "2026-11-26"


def test_a_chosen_date_shows_that_day(api):
    assert _board(api, "2026-11-26").json()["date"] == "2026-11-26"


def test_a_date_with_no_clinic_day_says_so(api):
    r = _board(api, "2026-12-25")
    assert r.status_code == 404
    assert r.json() == {"detail": "There is no clinic day on that date."}


@pytest.mark.parametrize("date", ["25/12/2026", "tomorrow"])
def test_a_date_that_isnt_a_date_is_refused(api, date):
    assert _board(api, date).status_code == 422


def test_a_case_added_for_the_demo_day_is_booked_on_it(api):
    r = _add(api, visit_date="2026-11-26", appointment_time="11:30")
    assert r.status_code == 201, r.text
    day = _board(api, "2026-11-26").json()
    assert [a["patient_id"] for a in day["appointments"]][-1] == "P100"
    assert day["appointments"][-1]["time"] == "11:30"
    assert day["counts"]["booked"] == 8


def test_appointments_are_listed_in_time_order(api):
    assert _add(api, visit_date="2026-11-26", appointment_time="08:00").status_code == 201
    times = [a["time"] for a in _board(api, "2026-11-26").json()["appointments"]]
    assert times == sorted(times) and times[0] == "08:00"


def test_a_case_for_a_new_date_opens_that_clinic_day_and_the_board_moves_to_it(api):
    r = _add(api, visit_date="2026-11-27", appointment_time="09:00")
    assert r.status_code == 201, r.text
    day = _board(api).json()  # today (2026-11-27) now has a clinic day
    assert (day["date"], day["clinic"], day["room"], day["clinician"]) == (
        "2026-11-27", "Demo ART Clinic", "Room 3", "Dr. A. Okello")
    assert [(a["time"], a["patient_id"]) for a in day["appointments"]] == [("09:00", "P100")]
    assert _board(api, "2026-11-26").json()["counts"]["booked"] == 7  # the demo day is untouched


def test_with_no_visit_date_the_case_is_booked_today(api):
    assert _add(api).status_code == 201
    assert _board(api).json()["date"] == "2026-11-27"


def test_two_patients_may_share_a_time(api):
    assert _add(api, visit_date="2026-11-26", appointment_time="08:40").status_code == 201
    day = _board(api, "2026-11-26").json()
    assert [a["patient_id"] for a in day["appointments"] if a["time"] == "08:40"] == ["P004", "P100"]


@pytest.mark.parametrize("body", [
    {"appointment_time": None},
    {"appointment_time": "9:00"},
    {"appointment_time": "24:00"},
    {"appointment_time": "09:60"},
    {"appointment_time": "09:00 "},
])
def test_an_appointment_time_is_needed_as_hh_mm(api, body):
    r = _add(api, **body) if body["appointment_time"] is not None else api.client.post(
        "/api/patients", json={"patient_id": "P100", "art_regimen": ["TLD"]}, headers=LOCAL)
    assert r.status_code == 422
    assert api.added_cases == []


def test_a_refused_case_books_nothing(api):
    assert _add(api, patient_id="P001", visit_date="2026-11-27").status_code == 409
    assert _board(api).json()["date"] == "2026-11-26"  # no clinic day was opened for the 27th
    with Session(api.engine) as s:
        assert clinic_db.day_on(s, datetime.date(2026, 11, 27)) is None


def test_the_case_and_its_booking_are_one_save(api, monkeypatch):
    """If the booking can't be saved, neither is the case."""
    def broken(session, **_):
        raise RuntimeError("the booking failed")

    monkeypatch.setattr(clinic_db, "booking_rows", broken)
    with pytest.raises(RuntimeError):
        _add(api)
    assert api.client.get("/api/patients/P100", headers=LOCAL).status_code == 404


def test_loading_the_demo_day_again_adds_nothing():
    from tests.api_fakes import memory_engine, read_clinic_day, read_patients
    from backend import patients_db

    engine = memory_engine()
    with Session(engine) as s:
        patients_db.import_records(s, read_patients(), origin="seed")
        assert clinic_db.import_schedule(s, read_clinic_day(), origin="seed") == 7
        assert clinic_db.import_schedule(s, read_clinic_day(), origin="seed") == 0


def test_a_schedule_booking_an_unknown_patient_is_refused():
    from tests.api_fakes import memory_engine, read_clinic_day

    bad = read_clinic_day()
    bad["appointments"].append({"time": "11:00", "patient_id": "NOPE"})
    with Session(memory_engine()) as s, pytest.raises(clinic_db.BadSchedule, match="NOPE"):
        clinic_db.import_schedule(s, bad, origin="seed")


def test_the_board_names_the_days_around_it(api):
    """Review, 2026-11-27: once a case is booked for today the board moves to today; the website
    reaches the demo day through previous_date."""
    assert _add(api, visit_date="2026-11-27").status_code == 201
    today = _board(api).json()
    assert (today["date"], today["previous_date"], today["next_date"]) == ("2026-11-27", "2026-11-26", None)
    demo = _board(api, today["previous_date"]).json()
    assert (demo["date"], demo["previous_date"], demo["next_date"], demo["counts"]["booked"]) == (
        "2026-11-26", None, "2026-11-27", 7)


def test_without_any_clinic_day_a_case_cant_be_booked(api):
    """A database whose backup was never loaded has no clinic to copy: the server isn't ready."""
    from sqlmodel import delete

    with Session(api.engine) as s:
        s.exec(delete(clinic_db.AppointmentRow))
        s.exec(delete(clinic_db.ClinicDayRow))
        s.commit()
    r = _add(api)
    assert r.status_code == 503
    assert r.json() == {"detail": "No clinic day is set up yet."}
    assert api.client.get("/api/patients/P100", headers=LOCAL).status_code == 404


def test_a_patient_is_booked_at_most_once_on_a_day():
    from sqlalchemy.exc import IntegrityError
    from tests.api_fakes import memory_engine, read_clinic_day, read_patients
    from backend import patients_db

    engine = memory_engine()
    with Session(engine) as s:
        patients_db.import_records(s, read_patients(), origin="seed")
        clinic_db.import_schedule(s, read_clinic_day(), origin="seed")
        s.add(clinic_db.AppointmentRow(date=datetime.date(2026, 11, 26), time="12:00", patient_id="P004",
                                       origin="added", booked_at=datetime.datetime.now(datetime.timezone.utc)))
        with pytest.raises(IntegrityError):
            s.commit()
