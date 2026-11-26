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


def test_an_alerts_values_are_the_labs_it_is_about() -> None:
    """The design's value box (owner, 2026-11-26: by code, no AI change): a rule's tests from a
    table, an AI alert's tests from its own words; the latest result on or before the visit."""
    import datetime

    from artemis.patient.labs import read_lab_entries
    from artemis.rules.checks import Alert
    from artemis.screen_text import alert_values

    patient = {"labs": {
        "creatinine": [{"date": "2024-10-01", "value": "88", "unit": "umol/L"}, {"date": "2027-01-01", "value": "99", "unit": "umol/L"}],
        "egfr": [{"date": "2026-01-05", "value": "52", "unit": "mL/min/1.73m2"}],
        "viral_load": [{"date": "2025-10-01", "value": "40", "unit": "copies/mL"}],
    }}
    labs = read_lab_entries(patient)
    visit = datetime.date(2026, 1, 22)
    rule = Alert("tdf_creatinine_overdue", "Creatinine monitoring overdue while on TDF", "m", {}, "q")
    assert alert_values(rule, labs, visit) == [
        {"label": "creatinine", "value": "88", "unit": "umol/L", "date": "2024-10-01"},
        {"label": "eGFR", "value": "52", "unit": "mL/min/1.73m2", "date": "2026-01-05"},
    ]
    ai = Alert("A1", "Missing Viral Load Monitoring", "The last VL was months ago.", {}, "q", source="ai")
    assert alert_values(ai, labs, visit) == [{"label": "viral load", "value": "40", "unit": "copies/mL", "date": "2025-10-01"}]
    words_only = Alert("A2", "Vivid dreams on efavirenz", "Sleep disturbance reported.", {}, "q", source="ai")
    assert alert_values(words_only, labs, visit) == []


def test_the_key_sentence_is_the_passage_sentence_closest_to_the_alert() -> None:
    from artemis.guidelines.vector_store import VectorSearchResult
    from artemis.rules.checks import Alert
    from artemis.screen_text import key_sentence

    passage = VectorSearchResult("c1", (
        "Table 12: MONITORING SCHEDULE | Test | Frequency\n"
        "Viral load testing is the preferred monitoring approach. "
        "Check viral load every 6 months for patients on DTG-based ART. "
        "Counsel on adherence."
    ), {"page_number": 32}, 0.1)
    alert = Alert("A1", "Missing viral load monitoring", "Viral load every 6 months is due on DTG-based ART.", {}, "q", source="ai")
    assert key_sentence(alert, [passage]) == "Check viral load every 6 months for patients on DTG-based ART."
    assert key_sentence(alert, []) is None
    unrelated = Alert("A2", "Vivid dreams", "Sleep disturbance.", {}, "q")
    assert key_sentence(unrelated, [passage]) is None


def test_the_key_sentence_comes_from_flowchart_and_bullet_text_too() -> None:
    """Passages are often one long line of flowchart or bullet text; "VL" means viral load."""
    from artemis.guidelines.vector_store import VectorSearchResult
    from artemis.rules.checks import Alert
    from artemis.screen_text import key_sentence

    text = ("Figure 4 outlines the virological monitoring of patients on DTG-based first-line ART. flowchart : "
            "Patient on two NRTIs + DTG Check VL every 6 months* *If VL suppressed for 1 year, can reduce to "
            "12 monthly - Provide enhanced adherence support - Repeat VL in 2-3 months")
    passage = VectorSearchResult("c1", text, {"page_number": 32}, 0.1)
    alert = Alert("A1", "Missing Viral Load Monitoring",
                  "Guidelines recommend viral load monitoring every 6 months for patients on DTG-based ART.", {}, "q", source="ai")
    assert key_sentence(alert, [passage]) == "Patient on two NRTIs + DTG Check VL every 6 months"
