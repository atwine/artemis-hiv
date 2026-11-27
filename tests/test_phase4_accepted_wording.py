"""The Phase 4 check's accepted rule wording (owner, 2026-11-27: "A, accept the wording").

Two fixed rules were reworded on purpose, so GLM's saved 2B run holds their old text and the
passages their old text found. The check swaps in the accepted new text and passages for those
fixed-rule alerts only; everything the AI said is still compared with the saved run as it is.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("check_phase4", ROOT / "scripts" / "check_phase4.py")
check_phase4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_phase4)

ACCEPTED = {
    "messages": {"tdf_nsaid_use": "New NSAID wording."},
    "passages": {"P005": {"tdf_nsaid_use": ["new_p1", "new_p2"]}},
}


def _record():
    return {
        "case_id": "P005",
        "alerts": [
            {"alert_id": "tdf_nsaid_use", "source": "rule", "title": "NSAID use", "message": "Old wording."},
            {"alert_id": "ALERT_001", "source": "ai", "title": "Kidney", "message": "AI words."},
        ],
        "retrieved": {"tdf_nsaid_use": ["old_p1"], "ALERT_001": ["ai_p1"]},
    }


def test_a_reworded_rule_alert_gets_the_accepted_text_and_passages():
    expected = check_phase4.with_accepted_rule_wording(_record(), ACCEPTED)
    assert expected["alerts"][0]["message"] == "New NSAID wording."
    assert expected["retrieved"]["tdf_nsaid_use"] == ["new_p1", "new_p2"]


def test_the_ai_alerts_and_the_saved_record_stay_as_they_were():
    record = _record()
    before = copy.deepcopy(record)
    expected = check_phase4.with_accepted_rule_wording(record, ACCEPTED)
    assert expected["alerts"][1] == before["alerts"][1]
    assert expected["retrieved"]["ALERT_001"] == ["ai_p1"]
    assert record == before


def test_another_case_keeps_its_saved_passages():
    record = {**_record(), "case_id": "MR-KS"}
    assert check_phase4.with_accepted_rule_wording(record, ACCEPTED)["retrieved"]["tdf_nsaid_use"] == ["old_p1"]


@pytest.mark.parametrize("accepted", [
    {"messages": {"ALERT_001": "Rewritten AI text."}, "passages": {}},
    {"messages": {}, "passages": {"P005": {"ALERT_001": ["x"]}}},
])
def test_accepting_new_wording_for_an_ai_alert_is_refused(accepted):
    with pytest.raises(ValueError, match="not a fixed-rule alert"):
        check_phase4.with_accepted_rule_wording(_record(), accepted)


def test_the_committed_file_accepts_only_the_two_reworded_rules():
    accepted = json.loads((ROOT / "eval" / "phase4" / "accepted-rule-wording.json").read_text(encoding="utf-8"))
    reworded = {"efv_sleep_disturbance", "tdf_nsaid_use"}
    assert set(accepted["messages"]) == reworded
    assert {aid for by_alert in accepted["passages"].values() for aid in by_alert} <= reworded
