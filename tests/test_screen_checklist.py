"""docs/screen-checklist.md stays complete: every AI-review result and status is listed there and has
banner wording, and a result outside the shared lists is refused (owner, 2026-11-26)."""

from __future__ import annotations

from pathlib import Path

import pytest

from artemis.screen_text import status_banners
from artemis.visit import AI_REVIEW_OUTCOMES, STATUSES, AnalysisResult

CHECKLIST = (Path(__file__).resolve().parents[1] / "docs" / "screen-checklist.md").read_text(encoding="utf-8")


def test_every_ai_review_result_and_status_is_in_the_checklist() -> None:
    for value in AI_REVIEW_OUTCOMES + STATUSES:
        assert f"| `{value}` |" in CHECKLIST, f"{value} is missing from docs/screen-checklist.md"


def test_every_ai_review_that_did_not_finish_cleanly_has_its_own_banner() -> None:
    for outcome in AI_REVIEW_OUTCOMES:
        if outcome in ("ok", "not_run"):
            continue
        banners = status_banners("INCOMPLETE", outcome, 0)
        assert len(banners) == 2 and banners[0][0] in ("warning", "error"), outcome


def test_every_status_has_a_banner() -> None:
    for status in STATUSES:
        for outcome in AI_REVIEW_OUTCOMES:
            assert status_banners(status, outcome, 1), (status, outcome)


def _result(**changes) -> AnalysisResult:
    values = dict(patient_id="P1", alerts=[], results=[], status="GREEN",
                  screening_outcome="ok", screening_ran=True, screening_debug=None, patient_summary=None,
                  agentic_enabled=False, agentic_result=None, agentic_reasoner=None, llm_error=None)
    values.update(changes)
    return AnalysisResult(**values)


def test_a_result_outside_the_shared_lists_is_refused() -> None:
    _result()  # a known result and status are accepted
    with pytest.raises(ValueError):
        _result(screening_outcome="timed_out")
    with pytest.raises(ValueError):
        _result(status="BLUE")


def test_an_unsaved_check_has_its_banner_and_is_in_the_checklist() -> None:
    """Owner, 2026-11-26: when a check can't be saved, the screen says so in this one wording."""
    from artemis.screen_text import RECORD_NOT_SAVED, record_banners

    assert RECORD_NOT_SAVED == "This check could not be saved, so its alerts cannot be decided here."
    assert record_banners(saved=False) == [("warning", RECORD_NOT_SAVED)]
    assert record_banners(saved=True) == []
    assert "`RECORD_NOT_SAVED`" in CHECKLIST
