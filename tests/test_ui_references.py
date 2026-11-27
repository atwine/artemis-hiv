"""Fix 8: an AI alert lists the passages it was shown and cited; a rule alert's are labelled as search results."""

from __future__ import annotations

from artemis.rules.checks import Alert
from artemis.guidelines.vector_store import VectorSearchResult
from artemis.screen_text import alert_references


def _chunk(cid: str, page: int) -> VectorSearchResult:
    return VectorSearchResult(chunk_id=cid, document="text", metadata={"page_number": page}, distance=0.1)


def _ai(citations) -> Alert:
    return Alert("A1", "t", "m", {"type": "llm_screening", "citations": citations}, "q", source="ai")


def test_an_ai_alert_lists_its_cited_passages_and_marks_unseen_ones() -> None:
    heading, lines = alert_references(
        _ai(
            [
                {"chunk_id": "c1", "page_number": 1, "shown_to_ai": True},
                {"chunk_id": "made_up", "page_number": 99, "shown_to_ai": False},
            ]
        ),
        [_chunk("c1", 7)],
    )
    assert "shown and cited" in heading
    # The page comes from the passage itself, not from the AI's claim.
    assert lines == ["Guidelines · p. 7", "Guidelines · p. 99: not among the passages the AI was given"]


def test_an_ai_alert_that_cited_nothing_says_so_in_its_heading() -> None:
    """Owner, 2026-11-27 ("A, say so"): the heading itself says it, and the website shows it as sent
    (screen wording comes from the backend)."""
    from artemis.screen_text import NO_PASSAGE_CITED

    assert NO_PASSAGE_CITED == "No guideline passage cited"
    assert alert_references(_ai([]), []) == (NO_PASSAGE_CITED, [])


def test_a_rule_alerts_passages_are_labelled_as_search_results() -> None:
    rule = Alert("R1", "t", "m", {}, "q")
    heading, lines = alert_references(rule, [_chunk("a", 3), _chunk("b", 3), _chunk("c", 5)])
    assert heading.startswith("Related passages")
    assert lines == ["Guidelines · p. 3", "Guidelines · p. 5"]
