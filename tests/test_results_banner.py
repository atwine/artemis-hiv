from __future__ import annotations

import pytest

from artemis.screen_text import status_banners


def _kinds(banners) -> list:
    return [k for k, _ in banners]


def _text(banners) -> str:
    return " ".join(t for _, t in banners)


@pytest.mark.parametrize("outcome", ["failed", "unreadable"])
def test_a_failed_ai_review_is_amber_and_never_green(outcome: str) -> None:
    b = status_banners("INCOMPLETE", outcome, 0)
    assert _kinds(b)[0] == "warning"
    assert "AI review failed" in _text(b)
    assert "success" not in _kinds(b)
    assert "not executed" not in _text(b)


def test_a_failed_ai_review_with_rule_alerts_shows_both() -> None:
    b = status_banners("AMBER", "unreadable", 1)
    assert "AI review failed" in b[0][1]
    assert b[1] == ("warning", "AMBER: 1 alert(s) to consider.")


def test_green_only_when_the_ai_review_worked() -> None:
    assert _kinds(status_banners("GREEN", "ok", 0)) == ["success"]
    off = status_banners("GREEN", "not_run", 0)
    assert _kinds(off) == ["info"] and "switched off" in _text(off)


def test_red_and_yellow_count_the_alerts() -> None:
    assert status_banners("RED", "ok", 3) == [("error", "RED: 3 alert(s) to consider (at least one high/critical issue).")]
    assert status_banners("AMBER", "ok", 2) == [("warning", "AMBER: 2 alert(s) to consider.")]


@pytest.mark.parametrize("outcome, reason", [("cut_off", "cut off"), ("partly_read", "could not be read")])
def test_an_incomplete_ai_review_says_alerts_may_be_missing(outcome: str, reason: str) -> None:
    b = status_banners("AMBER", outcome, 2)
    assert b[0][0] == "warning"
    assert reason in b[0][1] and "may be missing" in b[0][1]
    assert "AI review failed" not in _text(b)


def test_an_explanation_is_cut_back_to_its_plain_reason() -> None:
    """The screen shows only the reason, never the raw evidence or excerpts (owner, 2026-11-26:
    the API sends the same text, from this one function)."""
    from artemis.screen_text import plain_explanation

    raw = (
        "Why this alert: Creatinine last recorded 478 days ago. [chunk_id: x__p3_c1, page_number: 3]\n"
        "Patient evidence: {'regimen': ['TDF'], 'raw_issue': {'title': 'T'}}\n\n"
        "Guideline excerpts:\n- (page=255) Monitor creatinine every 12 months."
    )
    assert plain_explanation(raw) == "Creatinine last recorded 478 days ago."
    assert plain_explanation("") == ""
