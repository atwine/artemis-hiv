"""Phase 2B fix 5q: the AI lists the patient's own guideline questions first, and the screening searches with them."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, List, Optional

from artemis.patient.record import PatientContext

SUMMARY = {"art_regimen": "TDF/3TC/DTG", "pregnant": True}
CONTEXT = PatientContext(
    patient_id="T6", encounter_date=date(2026, 2, 24), art_regimen_current=["TDF", "3TC", "DTG"], notes_text="",
    latest_labs={}, dated_notes="2025-12-01: started ferrous sulfate 200 mg daily for anaemia in pregnancy.",
    lab_section="Creatinine 0.8 mg/dL (2025-11-20) -> 1.1 mg/dL (2026-02-20)",
)


class _Client:
    """A model that answers with a fixed reply and records what it was asked."""

    model = "fake"
    last_error: Optional[str] = None
    last_note = None
    last_finish_reason = "stop"

    def __init__(self, reply: Optional[str]) -> None:
        self.reply = reply
        self.asked: List[Any] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.asked.append((messages, format))
        return self.reply


def test_the_ai_is_shown_the_patient_and_asked_for_short_questions() -> None:
    from artemis.ai.search_questions import ask_search_questions

    from artemis.ai.screening import patient_facts

    client = _Client(json.dumps(["Can iron be taken with dolutegravir?", "When to check creatinine on TDF in pregnancy?"]))
    questions = ask_search_questions(client, patient_facts(CONTEXT, SUMMARY))
    assert questions == ["Can iron be taken with dolutegravir?", "When to check creatinine on TDF in pregnancy?"]
    messages, fmt = client.asked[0]
    asked = json.dumps(messages)
    assert "ferrous sulfate" in asked and "1.1 mg/dL" in asked   # the same notes and labs the screening reads
    assert fmt["type"] == "array" and fmt["maxItems"] == 6      # the reply format: at most 6 questions


def test_an_unusable_reply_gives_no_questions_so_the_generic_search_is_used() -> None:
    from artemis.ai.search_questions import ask_search_questions

    for reply in (None, "", "not json", json.dumps({"q": 1}), json.dumps(["", "   "])):
        assert ask_search_questions(_Client(reply), "facts") == []


def test_at_most_six_questions_are_kept_each_short_and_without_repeats() -> None:
    from artemis.ai.search_questions import ask_search_questions

    many = [f"Question {i}?" for i in range(9)] + ["Question 1?", "x" * 500]
    questions = ask_search_questions(_Client(json.dumps(many)), "facts")
    assert len(questions) == 6 and len(set(questions)) == 6 and all(len(q) <= 200 for q in questions)


class _R:
    def __init__(self, chunk_id: str) -> None:
        self.chunk_id = chunk_id


class _Rag:
    def __init__(self) -> None:
        self.searched: List[str] = []

    def search(self, text: str, top_k: Any = None) -> List[_R]:
        self.searched.append(text)
        return [_R(f"{text[:8]}-{i}") for i in range(top_k or 5)]

    def retrieve_for_alert(self, *, patient_context, alert, top_k=None):  # the generic search
        self.searched.append("GENERIC")
        return [_R(f"generic-{i}") for i in range(top_k or 5)]


def test_the_screening_searches_each_question_and_gets_two_passages_each_up_to_ten() -> None:
    from artemis.visit import screening_search

    rag = _Rag()
    questions = ["Can iron be taken with dolutegravir?", "When to check creatinine on TDF?", "Q3?", "Q4?", "Q5?", "Q6?"]
    result = screening_search(rag, context=CONTEXT, top_k=5, llm_client=_Client(json.dumps(questions)), summary=SUMMARY)
    found = result.passages
    assert rag.searched == questions and result.questions == questions
    assert len(found) == 10 and found[0].chunk_id.startswith("Can iron") and found[1].chunk_id.startswith("When to ")


def test_without_an_ai_or_its_questions_the_generic_search_stays() -> None:
    from artemis.visit import screening_search

    for client in (None, _Client("not json")):
        rag = _Rag()
        result = screening_search(rag, context=CONTEXT, top_k=5, llm_client=client, summary=SUMMARY)
        assert rag.searched == ["GENERIC"] and len(result.passages) == 5 and result.questions == []
