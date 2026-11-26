"""Phase 2B fix 5a2: the AI screening reads each guideline passage whole, not its first 480 characters."""

from __future__ import annotations

from datetime import date

from artemis.guidelines.vector_store import VectorSearchResult
from artemis.patient.record import PatientContext

LONG = ("Monitoring on TDF. " * 40) + "Check creatinine every 12 months while on TDF."  # the rule sits past 480 characters


class _Recorder:
    model = "fake"
    last_error = None
    last_note = None
    last_finish_reason = "stop"

    def __init__(self) -> None:
        self.prompts = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.prompts.append(" ".join(m["content"] for m in messages))
        return "[]"


def test_the_ai_sees_the_end_of_a_long_passage() -> None:
    from artemis.ai.screening import generate_llm_screening_alerts

    assert len(LONG) > 480 and LONG.index("Check creatinine") > 480
    client = _Recorder()
    context = PatientContext(patient_id="T1", encounter_date=date(2026, 11, 26), art_regimen_current=["TDF"],
                             notes_text="", latest_labs={})
    passage = VectorSearchResult("ug__p27_c1", LONG, {"page_number": 27, "source_path": "ug.md"}, 0.1)
    generate_llm_screening_alerts(patient_context=context, stage1_summary={}, screening_chunks=[passage], llm_client=client)
    assert "Check creatinine every 12 months while on TDF." in client.prompts[0]
