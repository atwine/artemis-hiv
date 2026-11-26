"""Reopening a saved visit, and a patient's past checks (plan step 2, unit 4).

Owner, 2026-11-26: read only, any saved visit. Reopening never calls the AI again.
"""

from __future__ import annotations

from artemis.screen_text import DISCLAIMER, FINALIZE_BLOCKED

LOCAL = {"Origin": "http://localhost:3000"}


def _check(api, patient_id="P001", **body):
    body.setdefault("note", "Routine follow-up. No issues.")
    r = api.client.post(f"/api/patients/{patient_id}/visits", json=body, headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def _reopen(api, visit_id):
    return api.client.get(f"/api/visits/{visit_id}", headers=LOCAL)


def test_a_reopened_visit_is_the_visit_as_it_was_shown(api):
    ran = _check(api, note="Mild headache since Monday.")
    calls = len(api.model.calls)
    r = _reopen(api, ran["visit_id"])
    assert r.status_code == 200, r.text
    back = r.json()
    assert len(api.model.calls) == calls  # no new AI call
    for key in ("visit_id", "patient_id", "visit_date", "saved_at", "status", "ai_review", "model", "cards", "plan", "banners", "disclaimer"):
        assert back[key] == ran[key], key
    assert back["note"] == "Mild headache since Monday."
    assert back["decisions"] == []
    assert back["finalized_at"] is None
    assert back["finalize_note"] == FINALIZE_BLOCKED
    assert back["disclaimer"] == DISCLAIMER


def test_a_reopened_visit_carries_its_decisions_and_finalize(api):
    ran = _check(api)
    decisions = [{"alert_id": c["extension"]["alert_id"], "action": "Acknowledge"} for c in ran["cards"]]
    api.client.post(f"/api/visits/{ran['visit_id']}/decisions", json={"decisions": decisions}, headers=LOCAL)
    final = api.client.post(f"/api/visits/{ran['visit_id']}/finalize", headers=LOCAL).json()
    back = _reopen(api, ran["visit_id"]).json()
    assert [d["alert_id"] for d in back["decisions"]] == [d["alert_id"] for d in decisions]
    assert back["unresolved"] == [] and back["all_resolved"] is True
    assert back["finalized_at"] == final["finalized_at"]
    assert back["finalize_note"] is None


def test_reopen_an_unknown_visit_is_404(api):
    assert _reopen(api, "nope").status_code == 404


def test_reopen_without_a_database_is_503(api):
    api.services.engine = None
    assert _reopen(api, "x").status_code == 503


def test_a_patients_past_checks_newest_first(api):
    first = _check(api, use_ai=False)
    second = _check(api)
    _check(api, patient_id="P002", use_ai=False)  # another patient's: not listed
    r = api.client.get("/api/patients/P001/visits", headers=LOCAL)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [v["visit_id"] for v in rows] == [second["visit_id"], first["visit_id"]]
    top = rows[0]
    assert set(top) == {"visit_id", "visit_date", "saved_at", "status", "ai_review", "ai_review_label", "ai_review_card_label",
                        "model", "alert_count", "decided_count", "finalized_at"}
    assert top["alert_count"] == len(second["cards"])
    assert top["decided_count"] == 0
    assert top["finalized_at"] is None


def test_past_checks_count_the_decisions(api):
    ran = _check(api)
    first = ran["cards"][0]["extension"]["alert_id"]
    api.client.post(f"/api/visits/{ran['visit_id']}/decisions",
                    json={"decisions": [{"alert_id": first, "action": "Acknowledge"}]}, headers=LOCAL)
    row = api.client.get("/api/patients/P001/visits", headers=LOCAL).json()[0]
    assert row["decided_count"] == 1


def test_past_checks_of_a_patient_with_none(api):
    assert api.client.get("/api/patients/P001/visits", headers=LOCAL).json() == []


def test_past_checks_of_an_unknown_patient_is_404(api):
    assert api.client.get("/api/patients/NOPE/visits", headers=LOCAL).status_code == 404
