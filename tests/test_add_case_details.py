"""The add-case form's visit details (plan for the add-case request, unit A1).

Owner, 2026-11-26: the form also takes the visit date, the visit type (decision 1: "A, four
choices"), previous ART with start and end dates, and today's clinical note. One shared builder
(artemis/patient/new_case.py) makes the record for both forms. Tests never write
Data/custom_patients.json.
"""

from __future__ import annotations

import datetime

import pytest

from artemis.patient.new_case import (
    VISIT_TYPES,
    CaseForm,
    PreviousArt,
    build_case_record,
)

LOCAL = {"Origin": "http://localhost:3000"}
TODAY = datetime.date(2026, 11, 26)
D = datetime.date


def _form(**kw):
    base = dict(patient_id="P100", art_regimen=["TLD"])
    base.update(kw)
    return CaseForm(**base)


def test_the_visit_types_are_the_owners_four():
    assert VISIT_TYPES == ("Routine review", "First visit", "Unscheduled visit", "Results review")


def test_the_visit_date_type_and_note_are_todays_visit():
    record, errors = build_case_record(
        _form(visit_date=D(2026, 11, 20), visit_type="Results review", todays_note="Came back for results.",
              complaints="Headache"),
        today=TODAY,
    )
    assert errors == []
    assert record["today_encounter"] == {
        "date": "2026-11-20", "visit_type": "Results review", "note": "Came back for results.",
        "orders": [], "med_changes": [],
    }
    assert record["visits"][0]["date"] == "2026-11-20"  # the intake note is dated on the visit


def test_with_no_visit_date_the_visit_is_today():
    record, _ = build_case_record(_form(), today=TODAY)
    assert record["today_encounter"]["date"] == "2026-11-26"
    assert "visit_type" not in record["today_encounter"]  # as cases were saved before
    assert "regimen_history" not in record


def test_previous_art_is_saved_as_regimen_history_in_drug_codes():
    record, errors = build_case_record(
        _form(previous_art=[PreviousArt(regimen=["TLE"], start_date=D(2018, 3, 1), end_date=D(2021, 6, 30)),
                            PreviousArt(regimen=["AZT", "3TC", "NVP"], start_date=D(2012, 1, 5), end_date=D(2018, 2, 28))]),
        today=TODAY,
    )
    assert errors == []
    # Oldest first, the way the record panel and the summary read it.
    assert record["regimen_history"] == [
        {"start_date": "2012-01-05", "end_date": "2018-02-28", "regimen": ["AZT", "3TC", "NVP"]},
        {"start_date": "2018-03-01", "end_date": "2021-06-30", "regimen": ["TDF", "3TC", "EFV"]},
    ]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"visit_type": "Drug refill only"}, "Visit type"),
        ({"previous_art": [PreviousArt(regimen=[], start_date=D(2018, 1, 1), end_date=D(2019, 1, 1))]}, "pick at least one drug"),
        ({"previous_art": [PreviousArt(regimen=["Aspirin"], start_date=D(2018, 1, 1), end_date=D(2019, 1, 1))]}, "not on it"),
        ({"previous_art": [PreviousArt(regimen=["TLE"], start_date=D(2019, 1, 1), end_date=D(2018, 1, 1))]}, "ends before it starts"),
        ({"previous_art": [PreviousArt(regimen=["TLE"], start_date=D(2018, 1, 1), end_date=D(2026, 12, 1))]}, "after the visit date"),
        ({"previous_art": [PreviousArt(regimen=["TLE"], start_date=D(2018, 1, 1), end_date=D(2019, 1, 1))] * 21}, "20"),
        ({"todays_note": "x" * 20001}, "20,000"),
    ],
)
def test_bad_visit_details_are_explained_and_not_built(change, message):
    record, errors = build_case_record(_form(**change), today=TODAY)
    assert record is None
    assert any(message in e for e in errors), errors


# The route


def _body(**kw):
    body = {"patient_id": "P100", "art_regimen": ["TLD"]}
    body.update(kw)
    return body


def test_add_a_case_with_its_visit_details_through_the_api(api):
    r = api.client.post("/api/patients", json=_body(
        visit_date="2026-11-20", visit_type="First visit", todays_note="New to this clinic.",
        previous_art=[{"regimen": ["TLE"], "start_date": "2018-03-01", "end_date": "2021-06-30"}],
    ), headers=LOCAL)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["today_encounter"]["date"] == "2026-11-20"
    assert body["today_encounter"]["visit_type"] == "First visit"
    assert body["today_encounter"]["note"] == "New to this clinic."
    assert body["regimen_history"] == [{"start_date": "2018-03-01", "end_date": "2021-06-30", "regimen": ["TDF", "3TC", "EFV"]}]
    listed = {p["patient_id"]: p for p in api.client.get("/api/patients", headers=LOCAL).json()}
    assert listed["P100"]["visit_date"] == "2026-11-20"


@pytest.mark.parametrize("change", [
    {"visit_type": "Drug refill only"},
    {"visit_date": "20/11/2026"},
    {"previous_art": [{"regimen": ["TLE"], "start_date": "2018-03-01"}]},  # previous ART needs its end date
    {"previous_art": [{"regimen": ["TLE"], "start_date": "2018-03-01", "end_date": "2021-06-30", "dose": "x"}]},
    {"previous_art": [{"regimen": ["x" * 21], "start_date": "2018-03-01", "end_date": "2021-06-30"}]},
    {"art_regimen": ["x" * 21]},  # a drug name is a pick from the list, never a long text
])
def test_bad_visit_details_are_refused_by_the_api(api, change):
    assert api.client.post("/api/patients", json=_body(**change), headers=LOCAL).status_code == 422
    assert api.added_cases == []


def test_the_form_offers_the_visit_types(api):
    choices = api.client.get("/api/form-choices", headers=LOCAL).json()
    assert choices["visit_types"] == list(VISIT_TYPES)


# The Streamlit form's previous-ART table (decision 2, 2026-11-27: "A, both forms")


def test_the_streamlit_tables_rows_become_previous_art():
    from artemis.patient.new_case import previous_art_from_rows

    art, errors = previous_art_from_rows([
        {"drugs": "tle", "start_date": "2018-03-01", "end_date": "2021-06-30"},
        {"drugs": "AZT, 3TC , NVP", "start_date": "2012-01-05", "end_date": "2018-02-28"},
        {"drugs": "", "start_date": "", "end_date": ""},  # the table's empty last row
    ])
    assert errors == []
    assert art == [
        PreviousArt(regimen=["TLE"], start_date=D(2018, 3, 1), end_date=D(2021, 6, 30)),
        PreviousArt(regimen=["AZT", "3TC", "NVP"], start_date=D(2012, 1, 5), end_date=D(2018, 2, 28)),
    ]


@pytest.mark.parametrize("row, message", [
    ({"drugs": "TLE", "start_date": "2018-03-01", "end_date": ""}, "start and an end date"),
    ({"drugs": "TLE", "start_date": "01/03/2018", "end_date": "2021-06-30"}, "YYYY-MM-DD"),
])
def test_a_bad_streamlit_row_is_explained(row, message):
    from artemis.patient.new_case import previous_art_from_rows

    art, errors = previous_art_from_rows([row])
    assert art == []
    assert any(message in e and "row 1" in e for e in errors), errors


def test_a_drug_not_on_the_list_is_kept_for_the_builder_to_explain():
    from artemis.patient.new_case import previous_art_from_rows

    art, errors = previous_art_from_rows([{"drugs": "Aspirin", "start_date": "2018-03-01", "end_date": "2021-06-30"}])
    assert errors == []
    _, build_errors = build_case_record(_form(previous_art=art), today=TODAY)
    assert any("not on it" in e for e in build_errors)


def test_a_row_with_no_drugs_is_explained_by_the_builder():
    from artemis.patient.new_case import previous_art_from_rows

    art, errors = previous_art_from_rows([{"drugs": "", "start_date": "2018-03-01", "end_date": "2021-06-30"}])
    assert errors == []
    _, build_errors = build_case_record(_form(previous_art=art), today=TODAY)
    assert any("pick at least one drug" in e and "row 1" in e for e in build_errors), build_errors
