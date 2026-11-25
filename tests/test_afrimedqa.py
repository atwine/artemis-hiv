"""Phase 2: the AfriMed-QA knowledge check picks the right questions, reads answers fairly, and resumes."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROWS = [
    # sample_id, question_type, specialty, tier, question, options, correct
    ("q1", "mcq", "Infectious_Disease", "expert", "Which fever?", {"option1": "Ebola", "option2": "Lassa"}, "option2"),
    ("q2", "mcq", "Pediatrics", "expert", "A child with HIV on ART has...", {"option1": "a", "option2": "b", "option3": "c"}, "option1,option3"),
    ("q3", "mcq", "Pediatrics", "expert", "Measles vaccine age?", {"option1": "9 months", "option2": "1 year"}, "option1"),
    ("q4", "saq", "Infectious_Disease", "expert", "Explain malaria.", {}, ""),
]


def _csv(tmp_path: Path) -> Path:
    path = tmp_path / "afrimedqa.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sample_id", "question_type", "specialty", "tier", "question", "question_clean", "answer_options", "correct_answer"])
        for sid, qt, sp, tier, q, opts, ans in ROWS:
            w.writerow([sid, qt, sp, tier, q, q, json.dumps(opts) if opts else "", ans])
    return path


def test_infectious_disease_and_hiv_questions_are_picked(tmp_path: Path) -> None:
    from artemis.evaluation.afrimedqa import load_questions

    qs = {q.sample_id: q for q in load_questions(_csv(tmp_path))}
    assert sorted(qs) == ["q1", "q2"]  # q3 is neither; q4 is not multiple choice
    assert (qs["q1"].hiv, qs["q2"].hiv) == (False, True)
    assert qs["q2"].correct == {"option1", "option3"} and qs["q2"].options["option3"] == "c"


@pytest.mark.parametrize("reply, keys", [
    ("option2", {"option2"}), ("The answer is option3.", {"option3"}), ("option1, option3", {"option1", "option3"}),
    ("Option 2", {"option2"}), ("", set()), (None, set()),
])
def test_answers_are_read_as_option_keys(reply, keys) -> None:
    from artemis.evaluation.afrimedqa import read_answer

    assert read_answer(reply) == keys


def test_a_question_counts_only_when_the_options_match_exactly(tmp_path: Path) -> None:
    from artemis.evaluation.afrimedqa import load_questions, score

    q2 = next(q for q in load_questions(_csv(tmp_path)) if q.sample_id == "q2")
    assert score(q2, {"option1", "option3"}) and not score(q2, {"option1"}) and not score(q2, set())


def test_answered_questions_are_skipped_on_resume(tmp_path: Path) -> None:
    from artemis.evaluation.afrimedqa import answered_ids, load_questions

    qs = load_questions(_csv(tmp_path))
    out = tmp_path / "model.jsonl"
    out.write_text(json.dumps({"sample_id": "q1"}) + "\n", encoding="utf-8")
    assert answered_ids(out) == {"q1"}
    assert [q.sample_id for q in qs if q.sample_id not in answered_ids(out)] == ["q2"]


def test_a_saved_row_holds_the_answer_but_never_the_question(tmp_path: Path) -> None:
    from artemis.evaluation.afrimedqa import load_questions, result_row

    q1 = next(q for q in load_questions(_csv(tmp_path)) if q.sample_id == "q1")
    row = result_row(q1, "option2", 0.001)
    assert (row["sample_id"], row["answer"], row["right"], row["cost_usd"]) == ("q1", ["option2"], True, 0.001)
    assert q1.text not in json.dumps(row) and "Lassa" not in json.dumps(row)


def test_accuracy_is_reported_for_all_hiv_and_infectious_disease_questions() -> None:
    from artemis.evaluation.afrimedqa import accuracy

    rows = [{"hiv": True, "specialty": "Pediatrics", "right": True},
            {"hiv": True, "specialty": "Infectious_Disease", "right": False},
            {"hiv": False, "specialty": "Infectious_Disease", "right": True}]
    assert accuracy(rows) == {"all": (2, 3), "hiv": (1, 2), "infectious_disease": (1, 2)}


def test_the_question_says_how_many_options_to_pick_and_the_format_allows_only_real_keys(tmp_path: Path) -> None:
    from artemis.evaluation.afrimedqa import answer_format, load_questions, messages

    qs = {q.sample_id: q for q in load_questions(_csv(tmp_path))}
    assert "single best option" in messages(qs["q1"])[0]["content"]
    assert "exactly 2 options" in messages(qs["q2"])[0]["content"]
    items = answer_format(qs["q2"])["properties"]["answer"]
    assert items["items"]["enum"] == ["option1", "option2", "option3"]
    assert (items["minItems"], items["maxItems"]) == (2, 2)
