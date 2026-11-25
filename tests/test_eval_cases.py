"""Phase 2: evaluation cases load, are checked where they enter, and their word rules match fairly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

KEYED = {
    "case_id": "T1",
    "source": "test",
    "patient": {"patient_id": "T1"},
    "answer_key": {
        "status": "draft, not checked by a clinician",
        "expect_clear": False,
        "problems": [
            {
                "id": "tdf_kidney",
                "kind": "drug_harm",
                "summary": "Kidney function falling on TDF",
                "match": [["creatinine", "egfr", "renal", "kidney"], ["tdf", "tenofovir"]],
                "guideline": {"document": "Uganda HIV guidelines", "page": 61, "quote": "Monitor renal function on TDF."},
            }
        ],
        "must_not": [{"id": "stop_art", "summary": "Stopping all ART", "match": [["stop all art", "discontinue art"]]}],
    },
}


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "case.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_case_loads_with_its_patient_and_answer_key(tmp_path: Path) -> None:
    from artemis.evaluation.cases import load_case

    case = load_case(_write(tmp_path, KEYED))
    assert case.case_id == "T1" and case.patient == {"patient_id": "T1"}
    assert [p.id for p in case.problems] == ["tdf_kidney"] and [m.id for m in case.must_not] == ["stop_art"]
    assert case.key_status.startswith("draft")


def test_a_word_rule_needs_every_group_and_matches_whole_word_starts() -> None:
    from artemis.evaluation.cases import MatchRule

    rule = MatchRule.from_json([["creatinine", "renal", "kidney"], ["tdf", "tenofovir"]])
    assert rule.matches("Rising creatinine on TDF")
    assert rule.matches("Kidneys: watch them on Tenofovir")  # case-insensitive, plural fine
    assert not rule.matches("Rising creatinine")  # the TDF group is missing
    assert not rule.matches("Adrenal crisis on TDF")  # "renal" inside "adrenal" doesn't count


@pytest.mark.parametrize(
    "change, reason",
    [
        (lambda k: k["problems"][0].update(kind="vibes"), "kind"),
        (lambda k: k.update(expect_clear=True), "expect_clear"),
        (lambda k: k["problems"][0].update(match=[]), "match"),
        (lambda k: k["problems"].append(dict(k["problems"][0])), "duplicate"),
    ],
)
def test_a_malformed_answer_key_is_refused(tmp_path: Path, change, reason: str) -> None:
    from artemis.evaluation.cases import CaseError, load_case

    data = json.loads(json.dumps(KEYED))
    change(data["answer_key"])
    with pytest.raises(CaseError, match=reason):
        load_case(_write(tmp_path, data))


def test_a_case_without_an_answer_key_yet_loads_but_says_so(tmp_path: Path) -> None:
    from artemis.evaluation.cases import load_case

    data = {k: v for k, v in KEYED.items() if k != "answer_key"}
    case = load_case(_write(tmp_path, data))
    assert case.key_status == "not written yet" and case.problems == [] and not case.expect_clear


def test_the_seven_test_patients_have_case_files_with_frozen_records() -> None:
    from artemis.evaluation.cases import load_cases

    sources = {}
    for name in ("mock_patients.json", "custom_patients.json"):
        for p in json.loads((ROOT / "Data" / name).read_text(encoding="utf-8")):
            sources[p["patient_id"]] = p
    cases = {c.case_id: c for c in load_cases(ROOT / "eval" / "cases")}
    for pid, patient in sources.items():
        assert pid in cases, pid
        assert cases[pid].patient == patient


def test_also_fine_items_load(tmp_path: Path) -> None:
    from artemis.evaluation.cases import load_case

    data = json.loads(json.dumps(KEYED))
    data["answer_key"]["also_fine"] = [{"id": "bp", "summary": "Blood pressure", "match": [["blood pressure"]]}]
    assert [a.id for a in load_case(_write(tmp_path, data)).also_fine] == ["bp"]
