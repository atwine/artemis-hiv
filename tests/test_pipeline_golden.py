"""The whole analysis, with a stand-in model and search, must match tests/golden/pipeline.json.

A difference means app behaviour changed. If the change is intended, rewrite the golden file
with `python tests/pipeline_harness.py golden` and explain the difference in the commit.
"""

from __future__ import annotations

import json

import pytest

from tests import pipeline_harness as h


@pytest.fixture(scope="module")
def actual() -> dict:
    return h.run_all()


@pytest.fixture(scope="module")
def expected() -> dict:
    return json.loads((h.GOLDEN_DIR / "pipeline.json").read_text(encoding="utf-8"))


def test_same_patients(actual: dict, expected: dict) -> None:
    assert sorted(actual) == sorted(expected)


@pytest.mark.parametrize("pid", sorted(json.loads((h.GOLDEN_DIR / "pipeline.json").read_text(encoding="utf-8"))))
def test_patient_matches_golden(pid: str, actual: dict, expected: dict) -> None:
    a, e = actual[pid], expected[pid]
    for key in e:
        assert a.get(key) == e[key], f"{pid}: '{key}' changed"


def test_a_planted_fault_is_caught(monkeypatch: pytest.MonkeyPatch, expected: dict) -> None:
    # Control: if the harness can't see a broken status colour, it can't see real changes either.
    monkeypatch.setattr(h.app, "_compute_overall_status", lambda alerts: "GREEN")
    patient = next(p for p in h.patients() if p["patient_id"] == "P001")
    assert h.run_patient(patient)["status"] != expected["P001"]["status"]
