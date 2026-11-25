"""Phase 2: the scoring counts caught, missed and extra alerts exactly, on answers we control."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from artemis.evaluation.cases import Case, Expected, MatchRule, MustNot

ROOT = Path(__file__).resolve().parents[1]


def _rule(*groups):
    return MatchRule.from_json([list(g) for g in groups])


KIDNEY = Expected("kidney", "drug_harm", "Kidney falling on TDF", _rule(("creatinine", "kidney", "renal"), ("tdf", "tenofovir")))
VL = Expected("vl", "monitoring", "Viral load overdue", _rule(("viral load",)))
STOP = MustNot("stop_art", "Stop all ART", _rule(("stop all art",)))
SICK = Case("S1", "test", {}, "draft", False, [KIDNEY, VL], [STOP])
CLEAR = Case("C1", "test", {}, "draft", True, [], [])


def _alert(title, message="", action="", source="ai", cited=()):
    return {"title": title, "message": message, "source": source,
            "evidence": {"recommended_action": action, "citations": [{"chunk_id": c, "shown_to_ai": s} for c, s in cited]}}


def test_a_run_counts_caught_missed_extra_and_must_not() -> None:
    from artemis.evaluation.scoring import score_run

    s = score_run(SICK, [
        _alert("Creatinine rising", "on tenofovir for 4 years"),
        _alert("Check blood pressure"),
        _alert("Toxicity", action="Stop all ART now"),
    ])
    assert (s.caught, s.missed, s.extra, s.alerts) == ({"kidney"}, {"vl"}, 2, 3)
    assert s.must_not_broken == {"stop_art"}
    assert [m.problems for m in s.matches] == [("kidney",), (), ()]


def test_one_alert_can_catch_two_problems_and_two_alerts_one() -> None:
    from artemis.evaluation.scoring import score_run

    s = score_run(SICK, [
        _alert("Renal decline on TDF; viral load due"),
        _alert("Kidney function", "TDF"),
    ])
    assert (s.caught, s.missed, s.extra) == ({"kidney", "vl"}, set(), 0)


def test_any_alert_on_a_case_that_should_be_clear_is_extra() -> None:
    from artemis.evaluation.scoring import score_run

    assert score_run(CLEAR, []).extra == 0
    s = score_run(CLEAR, [_alert("Viral load monitoring", source="ai"), _alert("Creatinine overdue", source="rule")])
    assert (s.extra, s.alerts, s.caught) == (2, 2, set())


def test_the_summary_numbers_and_their_counts() -> None:
    from artemis.evaluation.scoring import score_run, summarize

    runs = [
        score_run(SICK, [_alert("Creatinine on TDF")]),                              # caught 1 of 2, 0 extra
        score_run(SICK, [_alert("Creatinine on TDF"), _alert("Viral load overdue")]),  # caught 2 of 2
        score_run(CLEAR, []),                                                          # clear, correct
        score_run(CLEAR, [_alert("Something")]),                                       # clear, false alarm
    ]
    s = summarize(runs)
    assert (s.caught, s.expected, s.sensitivity) == (3, 4, 0.75)
    assert (s.matched_alerts, s.alerts, s.precision) == (3, 4, 0.75)
    assert (s.clear_correct, s.clear_runs, s.specificity) == (1, 2, 0.5)
    assert (s.must_not_broken_runs, s.must_not_runs) == (0, 2)
    # S1's two runs disagree (caught 1 vs 2), C1's two runs disagree (clear vs false alarm)
    assert s.consistency == 0.5


def test_no_runs_means_no_numbers_not_zeroes() -> None:
    from artemis.evaluation.scoring import summarize

    s = summarize([])
    assert (s.sensitivity, s.precision, s.specificity, s.consistency) == (None, None, None, None)


def _evaluate_module():
    spec = importlib.util.spec_from_file_location("evaluate", ROOT / "scripts" / "evaluate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_the_script_rebuilds_the_table_from_saved_runs(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    for case_id, key in (
        ("S1", {"expect_clear": False, "problems": [
            {"id": "kidney", "kind": "drug_harm", "summary": "Kidney", "match": [["creatinine"], ["tdf"]]},
            {"id": "vl", "kind": "monitoring", "summary": "VL", "match": [["viral load"]]}],
            "must_not": [{"id": "stop_art", "summary": "Stop all ART", "match": [["stop all art"]]}]}),
        ("C1", {"expect_clear": True}),
    ):
        (cases / f"{case_id}.json").write_text(json.dumps(
            {"case_id": case_id, "source": "test", "patient": {"patient_id": case_id}, "answer_key": {"status": "draft", **key}}))
    runs = tmp_path / "runs" / "model-a"
    runs.mkdir(parents=True)

    def run(case_id, k, alerts, cost=0.01, seconds=2.0, parse="parsed_nonempty"):
        (runs / f"{case_id}__run{k}.json").write_text(json.dumps({
            "case_id": case_id, "model": "model-a", "repeat": k, "seconds": seconds, "cost_usd": cost,
            "alerts": alerts, "screening": {"parse_status": parse}}))

    run("S1", 1, [_alert("Creatinine on TDF", cited=[("c1", True), ("c9", False)])])
    run("S1", 2, [_alert("Creatinine on TDF", cited=[("c1", True)]), _alert("Viral load overdue")])
    run("C1", 1, [], parse="parsed_empty")
    run("C1", 2, [_alert("Something")], parse="cut_off")

    ev = _evaluate_module()
    out = tmp_path / "results.md"
    assert ev.main(["--cases", str(cases), "--runs", str(tmp_path / "runs"), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "preliminary" in text.lower()
    row = next(line for line in text.splitlines() if line.startswith("| model-a"))
    for cell in ("75% (3/4)", "75% (3/4)", "50% (1/2)", "0/2", "50%", "67% (2/3)", "75% (3/4)", "$0.04"):
        assert cell in row, (cell, row)
    matches = (tmp_path / "matches.md").read_text(encoding="utf-8")
    assert "Viral load overdue -> vl" in matches and "missed: vl" in matches


def test_the_script_refuses_cases_without_an_answer_key(tmp_path: Path) -> None:
    cases = tmp_path / "cases"
    cases.mkdir()
    (cases / "X.json").write_text(json.dumps({"case_id": "X", "source": "t", "patient": {}}))
    (tmp_path / "runs" / "m").mkdir(parents=True)
    ev = _evaluate_module()
    with pytest.raises(SystemExit, match="no answer key"):
        ev.main(["--cases", str(cases), "--runs", str(tmp_path / "runs"), "--out", str(tmp_path / "r.md")])
