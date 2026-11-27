"""The add-case form's pick lists (plan for the add-case request, unit A3).

Owner, 2026-11-26: "A, this laptop only" (the same rule as every other route but health). The
lists are the ones the Streamlit form already uses, so a choice the website offers is one the
add-case route accepts.
"""

from __future__ import annotations

from artemis.patient.labs import TEST_NAMES, TEST_UNITS
from artemis.patient.medicines import REGIMEN_CHOICES

LOCAL = {"Origin": "http://localhost:3000"}


def _choices(api):
    r = api.client.get("/api/form-choices", headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_art_choices_are_the_forms_combinations_first(api):
    regimens = _choices(api)["art_regimens"]
    assert [r["choice"] for r in regimens] == REGIMEN_CHOICES
    by_choice = {r["choice"]: r["drugs"] for r in regimens}
    assert by_choice["TLD"] == ["TDF", "3TC", "DTG"]
    assert by_choice["TLE"] == ["TDF", "3TC", "EFV"]
    assert by_choice["DTG"] == ["DTG"]


def test_the_lab_tests_have_their_names_and_units_usual_first(api):
    tests = _choices(api)["lab_tests"]
    assert [t["test"] for t in tests] == list(TEST_UNITS)
    creatinine = next(t for t in tests if t["test"] == "creatinine")
    assert creatinine == {"test": "creatinine", "name": "creatinine", "units": ["umol/L", "mg/dL"]}
    assert all(t["name"] == TEST_NAMES[t["test"]] for t in tests)


def test_every_choice_offered_is_one_the_add_case_route_accepts(api):
    choices = _choices(api)
    # A value that makes sense in each unit (the form refuses a creatinine in the wrong unit).
    labs = [
        {"test": t["test"], "date": "2026-11-20", "value": "1.0" if unit == "mg/dL" else "90", "unit": unit,
         "when": "previous"}
        for t in choices["lab_tests"] for unit in t["units"]
    ]
    body = {"patient_id": "P100", "art_regimen": [r["choice"] for r in choices["art_regimens"]], "labs": labs,
            "appointment_time": "11:30"}
    r = api.client.post("/api/patients", json=body, headers=LOCAL)
    assert r.status_code == 201, r.text


def test_a_combination_is_saved_as_its_drugs(api):
    r = api.client.post("/api/patients", json={"patient_id": "P100", "art_regimen": ["TLD"], "appointment_time": "11:30"},
                        headers=LOCAL)
    assert r.status_code == 201, r.text
    tld = next(c["drugs"] for c in _choices(api)["art_regimens"] if c["choice"] == "TLD")
    assert r.json()["art_regimen_current"] == tld


def test_the_lists_need_no_model_or_database(api):
    api.services.engine = None
    assert _choices(api)["lab_tests"]
    assert api.model.calls == []
