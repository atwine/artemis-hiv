from __future__ import annotations

from datetime import date

from artemis.rules.checks import Alert
from modules.explanation_generator import generate_explanation
from artemis.patient.record import PatientContext
from modules.vector_store import VectorSearchResult


def _ctx() -> PatientContext:
    return PatientContext(
        patient_id="p1",
        encounter_date=date(2024, 1, 1),
        art_regimen_current=["TDF"],
        notes_text="Some clinical notes...",
        latest_labs={},
    )


def _alert() -> Alert:
    return Alert(
        alert_id="a1",
        title="Creatinine monitoring overdue while on TDF",
        message="Creatinine last recorded 500 days ago for a patient on TDF.",
        evidence={"regimen": ["TDF"], "days_since_creatinine": 500},
        query_hint="TDF renal function monitoring creatinine schedule",
    )


def test_explanation_quotes_the_retrieved_passages_with_page_and_no_chunk_id() -> None:
    retrieved = [
        VectorSearchResult(
            chunk_id="c1",
            document="Guideline: check creatinine at least annually for patients on TDF.",
            metadata={"page_number": 105},
            distance=0.12,
        )
    ]
    result = generate_explanation(patient_context=_ctx(), alert=_alert(), retrieved_chunks=retrieved)

    assert result.used_llm is False
    assert "Creatinine last recorded 500 days ago" in result.text
    assert "check creatinine at least annually" in result.text
    assert "(page=105)" in result.text
    assert "chunk_id" not in result.text and "c1" not in result.text
    assert result.used_chunks == retrieved


def test_explanation_says_when_no_passage_was_retrieved() -> None:
    result = generate_explanation(patient_context=_ctx(), alert=_alert(), retrieved_chunks=[])

    assert "Guideline excerpts: none retrieved" in result.text
    assert result.used_chunks == []
