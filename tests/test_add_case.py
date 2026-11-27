"""Adding a patient case (plan step 2, unit 6; plan item 4.6's suggestion).

Owner, 2026-11-26: add only; an ID already in use is refused; the old Streamlit form's rules,
with size limits; an optional name. The builder (artemis/patient/new_case.py) makes the case the
API saves, into the database only.
"""

from __future__ import annotations

import datetime
import json

import pytest

from artemis.patient.new_case import CaseForm, build_case_record

LOCAL = {"Origin": "http://localhost:3000"}
TODAY = datetime.date(2026, 11, 26)


def _form(**kw):
    base = dict(patient_id="P100", name="Grace Auma", age_years=40, sex="F", art_regimen=["TLD"],
                other_medications=["Amlodipine 5 mg daily"], complaints="Headache", examination_findings="BP 150/95",
                prior_history="Hypertension", lab_rows=[])
    base.update(kw)
    return CaseForm(**base)


# The shared builder


def test_a_case_is_built_from_the_form():
    record, errors = build_case_record(
        _form(lab_rows=[({"test": "creatinine", "date": "2026-11-26", "value": "88", "unit": "umol/L"}, "today")]),
        today=TODAY,
    )
    assert errors == []
    assert record["patient_id"] == "P100" and record["name"] == "Grace Auma"
    assert record["art_regimen_current"] == ["TDF", "3TC", "DTG"]
    assert record["other_medications"] == ["Amlodipine 5 mg daily"]
    assert record["labs"] == {"creatinine": [{"date": "2026-11-26", "value": "88", "unit": "umol/L", "source": "today"}]}
    assert record["today_encounter"] == {"date": "2026-11-26", "note": "", "orders": [], "med_changes": []}
    assert record["intake"] == {"complaints_symptoms": "Headache", "examination_findings": "BP 150/95", "prior_history": "Hypertension"}
    assert record["visits"][0]["type"] == "intake" and "Complaints & Symptoms:\nHeadache" in record["visits"][0]["clinician_note"]


def test_no_name_and_no_sex_are_left_out_as_before():
    record, _ = build_case_record(_form(name="", sex="", age_years=None), today=TODAY)
    assert "name" not in record
    assert record["sex"] is None and record["age_years"] is None


@pytest.mark.parametrize(
    "change, message",
    [
        ({"patient_id": ""}, "Patient ID is required."),
        ({"patient_id": "P/../1"}, "letters, numbers, spaces and dashes"),
        ({"patient_id": "P" * 41}, "letters, numbers, spaces and dashes"),
        ({"age_years": 121}, "Age"),
        ({"sex": "X"}, "Sex"),
        ({"art_regimen": ["Aspirin"]}, "ART"),
        ({"complaints": "x" * 5001}, "5,000"),
        ({"lab_rows": [({"test": "creatinine", "date": "26/11/2026", "value": "88", "unit": "umol/L"}, "today")]}, "YYYY-MM-DD"),
        ({"lab_rows": [({"test": "creatinine", "date": "2026-11-26", "value": "88", "unit": "umol/L"}, "today")] * 51}, "50"),
    ],
)
def test_a_bad_case_is_explained_and_not_built(change, message):
    record, errors = build_case_record(_form(**change), today=TODAY)
    assert record is None
    assert any(message in e for e in errors), errors


# The route


def _body(**kw):
    body = {"patient_id": "P100", "name": "Grace Auma", "age_years": 40, "sex": "F", "art_regimen": ["TLD"],
            "other_medications": [], "complaints": "", "examination_findings": "", "prior_history": "",
            "labs": [{"test": "viral_load", "date": "2026-08-01", "value": "<50", "unit": "copies/mL", "when": "previous"}],
            "appointment_time": "11:30"}
    body.update(kw)
    return body


def test_add_a_case_through_the_api(api):
    r = api.client.post("/api/patients", json=_body(), headers=LOCAL)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["patient_id"] == "P100" and body["name"] == "Grace Auma"
    assert body["labs"]["viral_load"] == [{"date": "2026-08-01", "value": "<50", "unit": "copies/mL", "source": "previous"}]
    assert api.added_cases[-1]["patient_id"] == "P100"
    listed = [p["patient_id"] for p in api.client.get("/api/patients", headers=LOCAL).json()]
    assert listed[-1] == "P100"


def test_an_id_already_in_use_is_refused(api):
    r = api.client.post("/api/patients", json=_body(patient_id="P001"), headers=LOCAL)
    assert r.status_code == 409
    assert r.json() == {"detail": "That patient ID is already in use."}
    assert api.added_cases == []


def test_a_bad_case_is_422_with_the_reasons(api):
    r = api.client.post("/api/patients", json=_body(labs=[{"test": "creatinine", "date": "2026-11-26", "value": "0.9", "unit": "umol/L", "when": "today"}]), headers=LOCAL)
    assert r.status_code == 422
    assert "looks like mg/dL" in json.dumps(r.json())
    assert api.added_cases == []


@pytest.mark.parametrize("extra", [{"labs_narrative": "x"}, {"today_encounter": {}}, {"source": "rule"}])
def test_fields_the_form_does_not_have_are_refused(api, extra):
    assert api.client.post("/api/patients", json=_body(**extra), headers=LOCAL).status_code == 422
    assert api.added_cases == []


def test_too_many_lab_rows_are_refused(api):
    rows = [{"test": "viral_load", "date": "2026-08-01", "value": "<50", "unit": "copies/mL", "when": "previous"}] * 51
    assert api.client.post("/api/patients", json=_body(labs=rows), headers=LOCAL).status_code == 422


def test_a_case_saved_without_a_sex_still_loads(api):
    """The Streamlit form saves sex as null when it's left blank; the patient list must still load."""
    r = api.client.post("/api/patients", json=_body(sex=None, name=None, age_years=None), headers=LOCAL)
    assert r.status_code == 201, r.text
    assert api.client.get("/api/patients", headers=LOCAL).status_code == 200


def test_each_medicine_line_has_a_length_limit(api):
    assert api.client.post("/api/patients", json=_body(other_medications=["a" * 201]), headers=LOCAL).status_code == 422
    record, errors = build_case_record(_form(other_medications=["a" * 201]), today=TODAY)
    assert record is None and any("200" in e for e in errors)


def test_services_built_without_a_writer_never_add_to_the_real_database():
    """Only default_services wires the real database; any other Services refuses to add a case."""
    from backend.services import Services

    services = Services(patients=list, search=lambda: None, model_client=lambda: None, engine=None, app_version="x")
    with pytest.raises(RuntimeError):
        services.add_case({"patient_id": "NEW"}, datetime.date(2026, 11, 27), "11:30")
