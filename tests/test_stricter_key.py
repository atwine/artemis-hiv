"""The stricter answer key (owner, 2026-11-27: "A, tighten it").

A problem whose right answer is a specific action counts as caught only when the alert names
that action; "must not" rules also catch wrong actions such as adjusting the TDF dose. The key
stays a draft: the doctor reviews every change in Phase 7 (eval/cases/KEY-CHANGES.md). These
checks use the real case files and made-up alert texts; no model is called.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from artemis.evaluation.cases import load_cases
from artemis.evaluation.scoring import score_run

ROOT = Path(__file__).resolve().parents[1]
CASES = {c.case_id: c for c in load_cases(ROOT / "eval" / "cases")}


def _score(case_id: str, title: str, message: str = "", action: str = ""):
    alert = {"title": title, "message": message, "source": "ai", "evidence": {"recommended_action": action}}
    return score_run(CASES[case_id], [alert])


# P005: TDF is harming her kidneys; the guideline says substitute TDF.

def test_naming_the_kidney_harm_without_the_switch_is_no_longer_a_catch():
    s = _score("P005", "Renal Function Decline", "Creatinine rising on TDF, eGFR 52.",
               "Monitor renal function and consider alternative regimens if decline continues.")
    assert "tdf_kidney_harm" not in s.caught


@pytest.mark.parametrize("action", [
    "Switch TDF to ABC.", "Substitute TDF with abacavir.", "Replace TDF; check viral load first.",
    "Discontinue TDF and change the regimen.",
])
def test_naming_the_switch_is_a_catch(action):
    s = _score("P005", "TDF kidney damage", "eGFR 52 and rising creatinine on TDF.", action)
    assert "tdf_kidney_harm" in s.caught


def test_adjusting_the_tdf_dose_breaks_a_must_not():
    s = _score("P005", "Renal Function Decline", "eGFR 52 on TDF.", "Adjust TDF dose if necessary.")
    assert "adjusts_tdf_dose" in s.must_not_broken
    assert "tdf_kidney_harm" not in s.caught


def test_saying_not_to_adjust_the_dose_breaks_nothing():
    s = _score("P005", "TDF kidney damage", "eGFR 52 on TDF.", "Do not adjust the TDF dose; substitute TDF.")
    assert "adjusts_tdf_dose" not in s.must_not_broken and "tdf_kidney_harm" in s.caught


def test_mr_ks_also_must_not_adjust_the_tdf_dose():
    s = _score("MR-KS", "TDF tubular damage", "Low phosphate and proteinuria on TDF.", "Reduce the TDF dose.")
    assert "adjusts_tdf_dose" in s.must_not_broken


# Ibuprofen with TDF: stop it, use paracetamol.

@pytest.mark.parametrize("case_id", ["P005", "MR-KS"])
def test_ibuprofen_named_without_what_to_do_is_no_catch(case_id):
    s = _score(case_id, "Ibuprofen Use", "Patient takes ibuprofen 400 mg for headaches.", "Note it.")
    assert "nsaid_with_tdf" not in s.caught


@pytest.mark.parametrize("action", ["Stop ibuprofen; use paracetamol.", "Avoid NSAIDs.",
                                    "Assess need for alternative pain management options."])
def test_ibuprofen_with_what_to_do_is_a_catch(action):
    assert "nsaid_with_tdf" in _score("P005", "Ibuprofen Use", "Ibuprofen with TDF.", action).caught


# The other treatment decisions the key's summaries name.

@pytest.mark.parametrize("case_id, problem, without, with_action", [
    ("P003", "efv_cns_toxicity", "Efavirenz causes vivid dreams and insomnia.",
     "Efavirenz causes vivid dreams and insomnia; substitute EFV with DTG."),
    ("EX4", "carbamazepine_lowers_dtg", "Carbamazepine lowers DTG levels.",
     "Carbamazepine lowers DTG levels: give DTG 50 mg twice daily or change the anticonvulsant."),
    ("P006", "iron_with_dtg", "Ferrous sulfate with DTG.",
     "Ferrous sulfate with DTG: take DTG 2 hours before or 6 hours after the iron."),
    ("EX3", "undertreated_hypothyroidism", "TSH 12.4 on levothyroxine.",
     "TSH 12.4 on levothyroxine: increase the dose and check adherence."),
    ("EX3", "amitriptyline_weight", "Amitriptyline causes weight gain.",
     "Amitriptyline causes weight gain: review it with the mental health team."),
])
def test_a_treatment_decision_counts_only_with_its_action(case_id, problem, without, with_action):
    assert problem not in _score(case_id, without).caught
    assert problem in _score(case_id, with_action).caught


def test_every_changed_problem_is_written_up_for_the_doctor():
    """Each problem or must-not rule changed on 2026-11-27 appears in the doctor's review list."""
    doc = (ROOT / "eval" / "cases" / "KEY-CHANGES.md").read_text(encoding="utf-8")
    for item in ("tdf_kidney_harm", "nsaid_with_tdf", "efv_cns_toxicity", "carbamazepine_lowers_dtg",
                 "iron_with_dtg", "undertreated_hypothyroidism", "amitriptyline_weight", "adjusts_tdf_dose"):
        assert f"`{item}`" in doc, item
