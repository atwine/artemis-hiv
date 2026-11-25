"""Explanation text shown under each alert.

Each alert gets a plain explanation built from the alert itself and the guideline passages
retrieved for it. No model call is made here. (The old model-written explanations, audit
checklist and synthesis modes were removed in Phase 1 fix 1; git history keeps them.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from modules.alert_rules import Alert
from artemis.patient.record import PatientContext
from modules.vector_store import VectorSearchResult


@dataclass
class ExplanationResult:
    text: str
    used_chunks: List[VectorSearchResult]
    used_llm: bool


def generate_explanation(
    *,
    patient_context: PatientContext,
    alert: Alert,
    retrieved_chunks: List[VectorSearchResult],
) -> ExplanationResult:
    """Explain an alert from its own text and up to three retrieved guideline passages."""

    used_chunks = list(retrieved_chunks[:3])
    return ExplanationResult(
        text=_fallback_explanation(patient_context, alert, used_chunks),
        used_chunks=used_chunks,
        used_llm=False,
    )


def _fallback_explanation(
    patient_context: PatientContext,
    alert: Alert,
    retrieved_chunks: List[VectorSearchResult],
) -> str:
    lines: List[str] = []
    lines.append(f"Why this alert: {alert.message}")
    lines.append(f"Patient evidence: {alert.evidence}")

    if retrieved_chunks:
        lines.append("\nGuideline excerpts:")
        for c in retrieved_chunks:
            page = c.metadata.get("page_number")
            excerpt = (c.document or "")[:350]
            # Rationale: clinician-facing fallback output should not include chunk_id.
            lines.append(f"- (page={page}) {excerpt}")
    else:
        lines.append("\nGuideline excerpts: none retrieved")

    return "\n".join(lines)
