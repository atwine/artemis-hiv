"""The plan step reads the patient's lab results, as the AI screening does (owner, 2026-11-27:
"Yes, fix it"). Found in a live visit: P005's only labs are a pasted lab note (creatinine 1.4,
eGFR 52), which the screening read but the plan's prompt left out, so the plan said "no lab
results are provided". The model is a stand-in: nothing is sent."""

from __future__ import annotations

import copy

from artemis.ai.client import ChatReply
from artemis.visit import management_plan, patient_context_for
from tests.api_fakes import fake_search, read_patients


class _Capture:
    model = "capture"

    def __init__(self) -> None:
        self.prompts = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.prompts.append(next(m["content"] for m in messages if m["role"] == "user"))
        return ChatReply("{}", finish_reason="stop")


def _plan_prompt(patient_id: str) -> str:
    patient = next(p for p in read_patients() if p["patient_id"] == patient_id)
    model = _Capture()
    management_plan(patient=copy.deepcopy(patient), today_note="", rag=fake_search(), llm_client=model)
    return model.prompts[0]


def test_the_plan_reads_lab_results_pasted_as_text():
    prompt = _plan_prompt("P005")
    assert "Creatinine: 1.4" in prompt and "eGFR: 52" in prompt


def test_the_plan_reads_the_same_lab_section_as_the_screening():
    for pid in ("P002", "P005"):
        patient = next(p for p in read_patients() if p["patient_id"] == pid)
        assert patient_context_for(patient, "").lab_section in _plan_prompt(pid), pid
