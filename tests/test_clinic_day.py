"""The demo clinic day board (plan step 2, unit 5).

Owner, 2026-11-26: the design's day (docs/design/content-kit.md), with P007-P009 added as drafted
stable patients; each patient's state comes from their latest saved check, whenever it ran.
"""

from __future__ import annotations

import json

LOCAL = {"Origin": "http://localhost:3000"}
DESIGN_DAY = [
    ("08:40", "P004", "Amina Nansubuga"), ("09:05", "P003", "Sam Kato"), ("09:30", "P005", "Rose Nabirye"),
    ("09:50", "P006", "Joan Nakato"), ("10:10", "P007", "Esther Nakimuli"), ("10:25", "P008", "Peter Okot"),
    ("10:40", "P009", "Ruth Akello"),
]


def _day(api):
    r = api.client.get("/api/clinic-day", headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def _row(day, patient_id):
    return next(a for a in day["appointments"] if a["patient_id"] == patient_id)


def _check(api, patient_id, **body):
    body.setdefault("note", "Routine follow-up.")
    r = api.client.post(f"/api/patients/{patient_id}/visits", json=body, headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_day_is_the_designs_day(api):
    day = _day(api)
    assert (day["clinic"], day["room"], day["clinician"], day["date"]) == ("Demo ART Clinic", "Room 3", "Dr. A. Okello", "2026-11-26")
    assert [(a["time"], a["patient_id"], a["name"]) for a in day["appointments"]] == DESIGN_DAY
    p005 = _row(day, "P005")
    assert (p005["age_years"], p005["sex"], p005["regimen"]) == (38, "F", "TDF/3TC/DTG")


def test_before_any_check_everyone_is_waiting(api):
    day = _day(api)
    assert {a["state"] for a in day["appointments"]} == {"waiting"}
    assert all(a["visit_id"] is None and a["status"] is None for a in day["appointments"])
    assert day["counts"] == {"booked": 7, "checked": 0, "finalized": 0, "left_in_red": 0}


def test_a_checked_patient_needs_you_until_finalized(api):
    visit = _check(api, "P004", use_ai=False)
    row = _row(_day(api), "P004")
    assert row["state"] == "needs_you"
    assert (row["visit_id"], row["status"], row["alert_count"], row["reviewed_count"]) == (
        visit["visit_id"], visit["status"], len(visit["cards"]), 0)
    decisions = [{"alert_id": c["extension"]["alert_id"], "action": "Acknowledge"} for c in visit["cards"]]
    api.client.post(f"/api/visits/{visit['visit_id']}/decisions", json={"decisions": decisions}, headers=LOCAL)
    assert _row(_day(api), "P004")["reviewed_count"] == len(decisions)
    final = api.client.post(f"/api/visits/{visit['visit_id']}/finalize", headers=LOCAL).json()
    row = _row(_day(api), "P004")
    assert row["state"] == "done"
    assert row["finalized_at"] == final["finalized_at"]
    assert _day(api)["counts"] == {"booked": 7, "checked": 1, "finalized": 1, "left_in_red": 0}


def test_the_latest_check_sets_the_state(api):
    first = _check(api, "P003", use_ai=False)
    second = _check(api, "P003", use_ai=False)
    assert _row(_day(api), "P003")["visit_id"] == second["visit_id"] != first["visit_id"]


def test_a_red_visit_not_finalized_is_left_in_red(api):
    from tests.api_fakes import FakeModel

    high = [{"alert_id": "X1", "title": "Severe rash on DTG", "message": "Stop and review today.",
             "issue_type": "toxicity", "severity": "high", "recommended_action": "Review today", "citations": []}]
    api.model = FakeModel({"screening": json.dumps(high)})
    visit = _check(api, "P005")
    assert visit["status"] == "RED"
    day = _day(api)
    assert _row(day, "P005")["status"] == "RED"
    assert day["counts"]["left_in_red"] == 1


def test_the_new_demo_patients_are_calm(api):
    for pid in ("P007", "P008", "P009"):
        assert _check(api, pid, use_ai=False)["cards"] == [], pid


def test_every_booked_patient_has_a_record(api):
    ids = {p["patient_id"] for p in api.client.get("/api/patients", headers=LOCAL).json()}
    assert {a["patient_id"] for a in _day(api)["appointments"]} <= ids


def test_a_booking_for_an_unknown_patient_is_reported(api):
    from tests.api_fakes import read_clinic_day

    bad = read_clinic_day()
    bad["appointments"].append({"time": "11:00", "patient_id": "NOPE"})
    api.services.clinic_day = lambda: bad
    r = api.client.get("/api/clinic-day", headers=LOCAL)
    assert r.status_code == 500
    assert r.json() == {"detail": "The clinic day could not be read."}


def test_a_malformed_schedule_is_reported(api):
    api.services.clinic_day = lambda: {"clinic": "x"}
    assert api.client.get("/api/clinic-day", headers=LOCAL).status_code == 500


def test_the_board_works_without_a_database(api):
    api.services.engine = None
    day = _day(api)
    assert {a["state"] for a in day["appointments"]} == {"waiting"}
