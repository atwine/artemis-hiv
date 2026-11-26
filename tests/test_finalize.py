"""Finalize (plan step 2, unit 3): closing a visit once every alert is decided.

Owner, 2026-11-26: a decision added after Finalize reopens the visit until it is finalized
again; every Finalize is kept. Finalizing twice with nothing changed saves nothing new.
"""

from __future__ import annotations

from sqlmodel import Session, select

from artemis.screen_text import FINALIZE_BLOCKED

LOCAL = {"Origin": "http://localhost:3000"}


def _check(api, **body):
    body.setdefault("note", "Routine follow-up. No issues.")
    r = api.client.post("/api/patients/P001/visits", json=body, headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def _decide_all(api, visit):
    decisions = [{"alert_id": c["extension"]["alert_id"], "action": "Acknowledge"} for c in visit["cards"]]
    r = api.client.post(f"/api/visits/{visit['visit_id']}/decisions", json={"decisions": decisions}, headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def _finalize(api, visit_id):
    return api.client.post(f"/api/visits/{visit_id}/finalize", headers=LOCAL)


def _finalize_rows(api, visit_id):
    from backend.records import VisitFinalize

    with Session(api.engine) as s:
        return s.exec(select(VisitFinalize).where(VisitFinalize.visit_id == visit_id).order_by(VisitFinalize.id)).all()


def test_finalize_is_refused_until_every_alert_is_decided(api):
    visit = _check(api)
    first = visit["cards"][0]["extension"]["alert_id"]
    api.client.post(f"/api/visits/{visit['visit_id']}/decisions",
                    json={"decisions": [{"alert_id": first, "action": "Acknowledge"}]}, headers=LOCAL)
    r = _finalize(api, visit["visit_id"])
    assert r.status_code == 422
    assert r.json() == {"detail": FINALIZE_BLOCKED}
    assert _finalize_rows(api, visit["visit_id"]) == []


def test_finalize_saves_the_time_and_the_decisions(api):
    visit = _check(api)
    _decide_all(api, visit)
    r = _finalize(api, visit["visit_id"])
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["visit_id"] == visit["visit_id"]
    assert body["finalized_at"]
    assert [d["alert_id"] for d in body["decisions"]] == [c["extension"]["alert_id"] for c in visit["cards"]]
    rows = _finalize_rows(api, visit["visit_id"])
    assert len(rows) == 1
    assert [d["alert_id"] for d in rows[0].decisions] == [d["alert_id"] for d in body["decisions"]]


def test_finalize_twice_saves_nothing_new(api):
    visit = _check(api)
    _decide_all(api, visit)
    first = _finalize(api, visit["visit_id"]).json()
    second = _finalize(api, visit["visit_id"])
    assert second.status_code == 200
    assert second.json() == first
    assert len(_finalize_rows(api, visit["visit_id"])) == 1


def test_a_decision_after_finalize_reopens_the_visit(api):
    visit = _check(api)
    _decide_all(api, visit)
    assert _finalize(api, visit["visit_id"]).status_code == 200
    first = visit["cards"][0]["extension"]["alert_id"]
    changed = api.client.post(
        f"/api/visits/{visit['visit_id']}/decisions",
        json={"decisions": [{"alert_id": first, "action": "Override", "reason": "Patient declined"}]}, headers=LOCAL,
    ).json()
    assert changed["finalized_at"] is None  # open again
    again = _finalize(api, visit["visit_id"])
    assert again.status_code == 200
    assert next(d for d in again.json()["decisions"] if d["alert_id"] == first)["reason"] == "Patient declined"
    assert len(_finalize_rows(api, visit["visit_id"])) == 2  # both kept


def test_decisions_reply_says_when_the_visit_is_finalized(api):
    visit = _check(api)
    body = _decide_all(api, visit)
    assert body["finalized_at"] is None
    final = _finalize(api, visit["visit_id"]).json()
    same = _finalize(api, visit["visit_id"]).json()
    assert same["finalized_at"] == final["finalized_at"]


def test_a_visit_with_no_alerts_can_be_finalized_at_once(api):
    from tests.api_fakes import read_patients

    calm = {**next(p for p in read_patients() if p["patient_id"] == "P001"),
            "labs": {"creatinine": [{"date": "2026-01-01", "value": "80", "unit": "umol/L"}]}}
    api.services.patients = lambda: [calm]
    visit = _check(api, use_ai=False)
    assert visit["cards"] == []
    r = _finalize(api, visit["visit_id"])
    assert r.status_code == 200
    assert r.json()["decisions"] == []


def test_finalize_an_unknown_visit_is_404(api):
    assert _finalize(api, "nope").status_code == 404


def test_finalize_without_a_database_is_503(api):
    api.services.engine = None
    assert _finalize(api, "anything").status_code == 503


def test_finalize_takes_no_body_fields(api):
    visit = _check(api)
    _decide_all(api, visit)
    r = api.client.post(f"/api/visits/{visit['visit_id']}/finalize", json={"finalized_at": "2020-01-01"}, headers=LOCAL)
    assert r.status_code == 422


def test_finalize_again_on_a_visit_imported_from_the_files(api, tmp_path):
    """A Finalize copied from the Streamlit files reads back like one made through the API."""
    from artemis import visit_record
    from backend import records
    from tests.test_visit_records_db import _checks, _finalized

    folder = tmp_path / "visit_records"
    for e in (_checks(), _finalized()):
        visit_record.append_entry(folder, e)
    with Session(api.engine) as s:
        records.import_folder(s, folder)
    r = _finalize(api, "v1")
    assert r.status_code == 200, r.text
    assert r.json()["finalized_at"] == "2026-11-20T08:05:00+00:00"
    assert r.json()["decisions"][0]["saved_at"] == "2026-11-20T08:05:00+00:00"


def test_two_finalizes_of_the_same_decisions_save_one_row(api):
    """Even if two Finalize calls race, the database keeps one row per set of decisions."""
    from backend import records

    visit = _check(api)
    _decide_all(api, visit)
    with Session(api.engine) as s:
        first = records.add_finalize(s, visit["visit_id"], [], finalized_at="2026-11-26T10:00:00+00:00")
        second = records.add_finalize(s, visit["visit_id"], [], finalized_at="2026-11-26T10:00:01+00:00")
        assert second.id == first.id
    assert len(_finalize_rows(api, visit["visit_id"])) == 1


def test_decision_and_finalize_times_have_the_same_shape_as_check_times(api):
    import re

    visit = _check(api)
    body = _decide_all(api, visit)
    final = _finalize(api, visit["visit_id"]).json()
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{6})?\+00:00$")
    for t in [visit["saved_at"], final["finalized_at"], *[d["saved_at"] for d in body["decisions"]]]:
        assert iso.match(t), t
