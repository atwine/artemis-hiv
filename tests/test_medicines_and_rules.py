"""Fix 5: drugs are recognised however they're typed, and the rules read the whole record."""

from __future__ import annotations

import copy

from artemis.patient.record import build_patient_context
from artemis.rules.checks import run_alerts
from tests import pipeline_harness as h


def _patient(pid: str) -> dict:
    return copy.deepcopy(next(p for p in h.patients() if p["patient_id"] == pid))


def _titles(patient: dict) -> list:
    return [a.title for a in run_alerts(build_patient_context(patient))]


def test_a_regimen_written_as_a_sentence_is_read_as_drugs() -> None:
    assert build_patient_context(_patient("P005")).art_regimen_current == ["TDF", "3TC", "DTG"]
    assert build_patient_context(_patient("Kintu-Test 001")).art_regimen_current == ["TDF", "3TC", "DTG"]
    assert build_patient_context(_patient("P006")).art_regimen_current == ["TDF", "3TC", "DTG"]


def test_tenofovir_rules_fire_for_p005_who_takes_ibuprofen() -> None:
    titles = _titles(_patient("P005"))
    assert "NSAID use mentioned while on TDF" in titles


def test_creatinine_only_in_pasted_text_is_not_called_missing() -> None:
    titles = _titles(_patient("P005"))
    assert "Creatinine missing while on TDF" not in titles
    assert "Creatinine recorded only as pasted text" in titles


def test_proteinuria_in_the_lab_text_is_seen_and_a_negative_is_not() -> None:
    assert "Proteinuria mentioned in notes" in _titles(_patient("P005"))  # "Urinalysis: Protein 1+"
    assert "Proteinuria mentioned in notes" not in _titles(_patient("P006"))  # "no protein"
    p = _patient("P001")
    p["today_encounter"]["note"] = "Dipstick done. No proteinuria."
    assert "Proteinuria mentioned in notes" not in _titles(p)


def test_a_regimen_typed_with_spaces_still_triggers_the_efavirenz_rule() -> None:
    p = _patient("P001")
    p["art_regimen_current"] = ["TDF", " 3TC", " EFV"]
    p["today_encounter"]["note"] = "Complains of insomnia since starting treatment."
    assert "Possible EFV neuropsychiatric side effects" in _titles(p)
    p["today_encounter"]["note"] = "Sleeping well. No complaints."
    assert "Possible EFV neuropsychiatric side effects" not in _titles(p)


def test_efavirenz_in_the_history_only_does_not_count_as_current() -> None:
    assert "EFV" not in build_patient_context(_patient("Kintu-Test 001")).art_regimen_current


def test_an_nsaid_on_the_medicine_list_is_seen() -> None:
    p = _patient("P001")
    p["other_medications"] = ["Ibuprofen 400 mg as needed"]
    assert "NSAID use mentioned while on TDF" in _titles(p)


def test_words_like_none_on_the_medicine_list_are_not_medicines() -> None:
    assert build_patient_context(_patient("P006")).other_medications == []
    assert build_patient_context(_patient("Kintu-Test 001")).other_medications == []
