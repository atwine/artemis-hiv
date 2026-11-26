"""Adding a patient case (plan step 2, unit 6; plan item 4.6's suggestion).

Owner, 2026-11-26: add only; an ID already in use is refused; the Streamlit form's rules, with
size limits; an optional name on both forms. One shared builder (artemis/patient/new_case.py)
makes the case for the Streamlit form and the API. Tests never write Data/custom_patients.json.
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


def test_a_case_is_built_like_the_streamlit_form_builds_it():
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
            "labs": [{"test": "viral_load", "date": "2026-08-01", "value": "<50", "unit": "copies/mL", "when": "previous"}]}
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


def test_the_real_writer_adds_to_the_file_and_keeps_the_rest(tmp_path):
    from backend.services import custom_case_writer
    from backend.settings import Settings

    path = tmp_path / "custom_patients.json"
    path.write_text(json.dumps([{"patient_id": "OLD"}]), encoding="utf-8")
    write = custom_case_writer(Settings(custom_patients_path=path))
    write({"patient_id": "NEW"})
    assert [p["patient_id"] for p in json.loads(path.read_text(encoding="utf-8"))] == ["OLD", "NEW"]


def test_the_real_writer_never_overwrites_an_unreadable_file(tmp_path):
    from artemis.patient.store import UnreadableFile
    from backend.services import custom_case_writer
    from backend.settings import Settings

    path = tmp_path / "custom_patients.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(UnreadableFile):
        custom_case_writer(Settings(custom_patients_path=path))({"patient_id": "NEW"})
    assert path.read_text(encoding="utf-8") == "{not json"
