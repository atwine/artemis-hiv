"""Agentic RAG orchestration skeleton (Phase 1).

This module defines the core data structures and a minimal orchestrator for a
"light decomposition" agentic RAG flow. The current implementation is a
non-invasive skeleton:

- it does not call the embedder, RagEngine, or LLM client yet
- it is not wired into the existing analysis pipeline
- it is safe to import and call, but only returns placeholder results

Later phases can extend the stubbed steps to integrate planning, per-sub-task
retrieval, reasoning, and verification.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from modules.embedder import Embedder
from artemis.ai.client import OllamaClient
from artemis.patient.record import build_patient_context, compute_lab_trends
from artemis.plan.plan_json import first_json_object, strip_code_fences, validate_plan
from modules.vector_store import VectorStore, VectorSearchResult


# Core data structures -----------------------------------------------------


@dataclass(frozen=True)
class QueryContext:
    """Normalized view of a user query and associated patient data.

    This is the primary object passed between agentic steps.
    """

    question_text: str
    patient_raw: Dict[str, Any]
    patient_summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SubTaskPlan:
    """One planning unit produced by the Planner agent.

    Phase 1 uses this as a structural placeholder; fields will be populated by a
    real planning step in Phase 2.
    """

    name: str
    description: str
    retrieval_query: str
    priority: str = "medium"


@dataclass
class EvidenceBundle:
    """Container for evidence retrieved for a given sub-task.

    In later phases, ``chunks`` will be populated from the vector store
    retrieval; for now this remains an empty placeholder.
    """

    subtask_name: str
    chunks: List[Any] = field(default_factory=list)
    summary: Optional[str] = None


@dataclass
class AgenticResult:
    """Final result of an agentic flow run.

    ``debug_info`` is intended for logs or future debug UI and may contain any
    intermediate artefacts (plans, evidence, verifier reports, etc.).
    """

    updated_management_plan_text: Optional[str] = None
    # What the plan failed in the app's own checks, after its retries; empty when it passed (fix 7).
    plan_issues: List[str] = field(default_factory=list)
    used_chunks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    debug_info: Dict[str, Any] = field(default_factory=dict)


# Stubbed agentic steps ----------------------------------------------------


def _normalize_input(context: QueryContext) -> QueryContext:
    """Phase 1 input normalization stub.

    Later phases may:
    - derive a structured patient summary from ``patient_raw``
    - enrich ``metadata`` with additional routing information

    For now, the input context is returned unchanged to keep behaviour explicit
    and deterministic.
    """

    return context


def _plan_subtasks(context: QueryContext) -> List[SubTaskPlan]:
    """Patient-aware planner for toxicity-focused light decomposition.

    Rationale: instead of always asking the same generic question, the planner
    inspects the patient's current drugs and creates a targeted retrieval
    sub-task *per drug* so the vector store returns the most relevant guideline
    sections about each drug's known side effects and toxicity markers.  It also
    adds a symptom-to-toxicity matching task and a doctor's-plan gap check.
    """

    question = (context.question_text or "").strip()
    if not question:
        question = "Clinical guideline support for this patient."

    subtasks: List[SubTaskPlan] = []

    # --- Suggestion 3: per-drug toxicity retrieval ---
    # Rationale: pulling guideline sections per drug maximizes the chance of
    # surfacing drug-specific side effects, monitoring requirements, and
    # switching criteria that a generic query would miss.
    regimen: List[str] = []
    try:
        regimen = list(context.patient_raw.get("art_regimen_current") or [])
    except Exception:
        pass

    for drug in regimen:
        subtasks.append(
            SubTaskPlan(
                name=f"drug_toxicity_{drug}",
                description=(
                    f"Retrieve guideline sections about known side effects, "
                    f"toxicity markers, monitoring requirements, and switching "
                    f"criteria for {drug}."
                ),
                retrieval_query=(
                    f"{drug} side effects toxicity monitoring renal hepatic "
                    f"haematological switching criteria contraindications"
                ),
                priority="high",
            )
        )

    # --- Symptom-to-toxicity matching task ---
    # Rationale: the doctor may have documented symptoms (e.g. fatigue, bone
    # pain, reduced urine output) that could be early signs of drug toxicity.
    # This sub-task retrieves guideline content about symptom-based toxicity
    # recognition so the LLM can cross-check patient symptoms against known
    # drug side effects.
    subtasks.append(
        SubTaskPlan(
            name="symptom_toxicity_match",
            description=(
                "Retrieve guideline sections that describe how specific "
                "symptoms (e.g. fatigue, bone pain, rash, reduced urine, "
                "nausea, peripheral neuropathy) can indicate ART drug "
                "toxicity, and how to confirm each suspected toxicity."
            ),
            retrieval_query=(
                f"{question}\n\n"
                "Focus on: which symptoms indicate drug toxicity, how to "
                "confirm suspected toxicity with lab tests, and what "
                "confirmatory investigations are recommended."
            ),
            priority="high",
        )
    )

    # --- Suggestion 4: doctor's plan gap check ---
    # Rationale: the user's workflow explicitly states that MedGemma should run
    # *after* the doctor has made a plan, and flag anything the plan missed.
    # This sub-task retrieves guideline actions so the LLM can compare them
    # against the doctor's documented plan.
    subtasks.append(
        SubTaskPlan(
            name="doctors_plan_check",
            description=(
                "Retrieve guideline sections about recommended clinical "
                "actions, required monitoring, counselling, and follow-up "
                "so the system can compare them against the doctor's "
                "current plan and flag any gaps."
            ),
            retrieval_query=(
                f"{question}\n\n"
                "Focus on: recommended actions after identifying drug "
                "toxicity, required lab monitoring intervals, patient "
                "counselling, when to switch regimen, and follow-up timing."
            ),
            priority="medium",
        )
    )

    return subtasks


def _retrieve_evidence(
    context: QueryContext,
    subtasks: List[SubTaskPlan],
    *,
    embedder: Embedder,
    vector_store: VectorStore,
    top_k: int = 5,
) -> List[EvidenceBundle]:
    """Retrieve evidence for each sub-task using the existing vector store.

    This function reuses the established embedding + vector-store stack
    (``Embedder`` + ``VectorStore``) and constructs a query per sub-task that
    incorporates the user question and, when possible, a brief patient
    context derived from ``patient_raw``.
    """

    if not subtasks:
        return []

    # Build a lightweight patient context for query enrichment; fall back to
    # question-only retrieval if parsing fails or patient data is incomplete.
    patient_notes: str = ""
    regimen: str = ""
    encounter_date: str = ""
    try:
        patient_ctx = build_patient_context(context.patient_raw)
        regimen = ", ".join(patient_ctx.art_regimen_current) or "unknown regimen"
        patient_notes = (patient_ctx.notes_text or "").strip()
        encounter_date = patient_ctx.encounter_date.isoformat()
    except Exception:
        patient_ctx = None  # type: ignore[assignment]

    notes_excerpt = patient_notes if patient_notes else ""

    bundles: List[EvidenceBundle] = []

    for subtask in subtasks:
        parts: List[str] = []
        if context.question_text:
            parts.append(f"Question: {context.question_text.strip()}")
        if regimen or encounter_date:
            parts.append(
                f"Patient regimen: {regimen or 'unknown'}; "
                f"Encounter date: {encounter_date or 'unknown'}"
            )
        if notes_excerpt:
            parts.append(f"Patient notes excerpt: {notes_excerpt}")

        # Include the sub-task description and retrieval hint so the query text
        # remains transparent and auditable.
        parts.append(f"Subtask: {subtask.name}")
        parts.append(f"Subtask description: {subtask.description}")
        if subtask.retrieval_query:
            parts.append(f"Subtask retrieval focus: {subtask.retrieval_query}")

        query_text = "\n".join(parts).strip()
        if not query_text:
            continue

        results: List[VectorSearchResult] = vector_store.query(
            query_text=query_text,
            embedder=embedder,
            top_k=top_k,
        )

        bundles.append(EvidenceBundle(subtask_name=subtask.name, chunks=list(results)))

    return bundles


def _reason_updated_management_plan(
    context: QueryContext,
    evidence_bundles: List[EvidenceBundle],
    *,
    llm_client: Optional[OllamaClient] = None,
) -> tuple:
    """(plan text or None, the checks it failed). The issues list is empty when the plan passed."""
    if llm_client is None:
        return None, []

    # A verdict on every item makes the plan longer; 400 tokens risked cutting it off (fix 7).
    _PLAN_CHAT_OPTIONS = {"num_predict": 1000}
    _strip_code_fences = strip_code_fences
    _extract_first_json_object = first_json_object
    _validate_plan_json = validate_plan

    def _organize_plan_json(
        *,
        draft_json_text: str,
        validation_issues: List[str],
    ) -> Optional[str]:
        # Rationale: act as a small "organizer agent" that repairs common
        # structure problems (duplicates, task-like problems, ordering) while
        # keeping the schema unchanged.
        if not draft_json_text.strip():
            return None

        messages = _build_plan_messages(
            retry_feedback=(
                "Draft plan JSON must be reorganized and repaired. Issues: "
                + ", ".join(validation_issues)
                + "\n\n"
                "If the draft is incomplete or invalid, you MUST rebuild a complete, valid plan JSON from scratch. "
                "You MUST de-duplicate repeated problems, merge overlapping ones, "
                "and rewrite problem titles as patient problems/clinical decisions (not tasks). "
                "Order problems from most urgent/high-risk to least. "
                "You MUST include a valid art_regimen_decision with decision one of: Switch, Hold temporarily, Continue, Uncertain. "
                "You MUST include clinician_plan_for_this_problem with a decision for every problem. "
                "Keep the plan concise (max 6 problems). "
                "Return ONLY the corrected JSON object."
            )
        )

        # Provide the draft JSON as additional context (user message) so the
        # organizer can repair it deterministically.
        messages = list(messages) + [
            {
                "role": "user",
                "content": (
                    # Rationale: provide only the JSON object (when present) to reduce confusion.
                    "Draft management plan JSON (repair this):\n"
                    + (_extract_first_json_object(draft_json_text) or _strip_code_fences(draft_json_text))
                ),
            }
        ]

        repaired = llm_client.chat(
            messages,
            format="json",
            options_override=_PLAN_CHAT_OPTIONS,
        )
        if repaired is None:
            return None
        repaired = _strip_code_fences(repaired)
        issues = _validate_plan_json(repaired)
        if issues:
            return None
        # Rationale: return only the extracted JSON so downstream renderers don't see extra text.
        return _extract_first_json_object(repaired) or repaired

    def _build_plan_messages(*, retry_feedback: Optional[str] = None) -> List[Dict[str, str]]:
        system_text = (
            "You are an HIV clinician assistant. Using ONLY the provided guideline excerpts and "
            "the patient data in the user message, produce an UPDATED MANAGEMENT PLAN.\n\n"
            "CRITICAL OUTPUT RULES:\n"
            "- BE CONCISE. Keep all text fields brief and action-oriented.\n"
            "- Output ONLY a single JSON object. Do NOT output markdown, code fences, or any extra text.\n"
            "- Do NOT include analysis, thinking, rationale preambles, or meta commentary.\n"
            "- Do NOT output any placeholders or template examples.\n"
            "- Problems must be PATIENT PROBLEMS / CLINICAL DECISIONS (not tasks like 'Assess', 'Check', 'Review').\n"
            "- Every Action must be specific enough that a clinician can act on it.\n"
            "- Every Reason must be ONE SENTENCE using patient facts and guideline excerpts.\n"
            "- If you cannot justify an action from the excerpts, write: Uncertain: why you are uncertain (do not guess).\n"
            "- Compare every problem with the clinician's assessment and plan for today, and give a verdict for every problem.\n\n"
            "REQUIRED JSON KEYS (root object):\n"
            "- art_regimen_decision: object with keys decision + reason (decision must be exactly one of: Switch, Hold temporarily, Continue, Uncertain)\n"
            "- problems: array of problem objects (maximum 3-5 items in priority order)\n"
            "- monitoring_plan: brief bullet points or string (what labs, when, triggers)\n"
            "- patient_counselling: array of brief strings (maximum 3-4 items)\n\n"
            "REQUIRED KEYS (art_regimen_decision):\n"
            "- decision: one of Switch, Hold temporarily, Continue, Uncertain (use Uncertain when the excerpts and patient data are not enough)\n"
            "- reason: brief 1-sentence rationale (patient facts + guideline-grounded OR Uncertain: ...)\n\n"
            "REQUIRED KEYS (each item in problems):\n"
            "- problem: string (a real patient problem / clinical decision)\n"
            "- action: string (specific action OR Uncertain: ...)\n"
            "- reason: brief 1-sentence rationale (patient facts + guideline-grounded OR Uncertain: ...)\n"
            "- clinician_plan_for_this_problem: object, required for every problem\n"
            "  - decision: one of Agree (the clinician's plan already covers it), Disagree (the plan does something else), "
            "Gap (the plan covers it partly), Not Addressed (the plan does not mention it, or there is no plan)\n"
            "  - explanation: brief 1-sentence explanation\n"
        )

        if retry_feedback:
            system_text += (
                "\n\nFORMAT FIX REQUIRED:\n"
                f"{retry_feedback}\n"
                "Rewrite the plan to fully comply. Output ONLY the corrected plan."
            )

        patient = context.patient_raw or {}
        question = (context.question_text or "").strip() or (
            "Clinical guideline support for this patient."
        )
        patient_id = patient.get("patient_id")

        lab_trends_text = ""
        try:
            raw_labs = patient.get("labs") or {}
            encounter_date_str = (patient.get("today_encounter") or {}).get("date")
            enc_date = None
            if encounter_date_str:
                from datetime import datetime as _dt
                enc_date = _dt.strptime(encounter_date_str, "%Y-%m-%d").date()
            trends = compute_lab_trends(raw_labs, encounter_date=enc_date)
            if trends:
                lab_trends_text = "\n".join(t.summary_text for t in trends)
        except Exception:
            lab_trends_text = ""

        doctors_plan = ""
        try:
            today = patient.get("today_encounter") or {}
            plan_parts: List[str] = []
            note = (today.get("note") or "").strip()
            if note:
                plan_parts.append(f"Today's note: {note}")
            orders = today.get("orders") or []
            if orders:
                plan_parts.append(f"Orders: {orders}")
            med_changes = today.get("med_changes") or []
            if med_changes:
                plan_parts.append(f"Medication changes: {med_changes}")
            doctors_plan = "\n".join(plan_parts) if plan_parts else "No plan documented."
        except Exception:
            doctors_plan = "No plan documented."

        regimen_str = ", ".join(build_patient_context(patient).art_regimen_current) or "unknown"
        # The same dated notes and recorded-facts summary the screening step reads (fixes 4 and 6).
        ctx = build_patient_context(patient)
        notes_text = ctx.dated_notes or ""
        summary_text = json.dumps(context.patient_summary or {}, ensure_ascii=False, default=str)

        evidence_lines: List[str] = []
        for bundle in evidence_bundles:
            chunks = list(bundle.chunks or [])
            if not chunks:
                continue
            evidence_lines.append(f"Subtask {bundle.subtask_name}:")
            # Rationale: keep the evidence snippet short to reduce the chance the LLM output
            # is cut off mid-plan.
            for r in chunks[:1]:
                try:
                    metadata = getattr(r, "metadata", {}) or {}
                    page = metadata.get("page_number")
                    chunk_id = getattr(r, "chunk_id", None)
                    doc_text = getattr(r, "document", "") or ""
                except Exception:
                    continue
                preview = doc_text.replace("\n", " ")
                if len(preview) > 200:
                    preview = preview[:200] + "…"
                evidence_lines.append(f"- page {page}, chunk {chunk_id}: {preview}")
            evidence_lines.append("")
        evidence_text = "\n".join(evidence_lines) or "No evidence retrieved."

        return [
            {"role": "system", "content": system_text},
            {
                "role": "user",
                "content": (
                    f"Patient id: {patient_id}\n"
                    f"Current regimen: {regimen_str}\n"
                    f"Question: {question}\n\n"
                    f"Patient summary (recorded facts; not_recorded lists empty fields):\n{summary_text}\n\n"
                    f"Patient notes, oldest first:\n{notes_text}\n\n"
                    f"Lab trends:\n{lab_trends_text or 'No lab history available.'}\n\n"
                    f"Doctor's current plan:\n{doctors_plan}\n\n"
                    f"Guideline excerpts:\n{evidence_text}"
                ),
            },
        ]

    try:
        messages = _build_plan_messages()
        plan_answer = llm_client.chat(
            messages,
            format="json",
            options_override=_PLAN_CHAT_OPTIONS,
        )
        if plan_answer is None:
            return None, ["no_reply"]

        issues = _validate_plan_json(plan_answer)
        if not issues:
            # Rationale: return only the JSON object (ignore any extra words around it).
            return _extract_first_json_object(plan_answer) or _strip_code_fences(plan_answer), []

        # One retry with explicit format feedback (non-blocking if it still fails).
        feedback = "Previous output failed validation: " + ", ".join(issues)
        retry_messages = _build_plan_messages(retry_feedback=feedback)
        plan_retry = llm_client.chat(
            retry_messages,
            format="json",
            options_override=_PLAN_CHAT_OPTIONS,
        )
        if plan_retry is None:
            return plan_answer, issues

        retry_issues = _validate_plan_json(plan_retry)
        if not retry_issues:
            # Rationale: return only the JSON object (ignore any extra words around it).
            return _extract_first_json_object(plan_retry) or _strip_code_fences(plan_retry), []

        # Organizer pass: attempt to repair/organize into a valid, de-duplicated
        # management plan JSON.
        organized = _organize_plan_json(
            draft_json_text=plan_retry,
            validation_issues=retry_issues,
        )
        if organized is not None:
            return organized, []

        # Still invalid: return the latest output with what it failed, so the screen can say so.
        return _strip_code_fences(plan_retry), retry_issues
    except Exception as exc:
        return None, [f"error:{exc.__class__.__name__}"]


# Public orchestrator ------------------------------------------------------


def run_agentic_flow(
    context: QueryContext,
    *,
    embedder: Embedder,
    vector_store: VectorStore,
    top_k: int = 5,
    llm_client: Optional[OllamaClient] = None,
) -> AgenticResult:
    """Run the Phase 1 agentic flow skeleton.

    Current behaviour:
    - normalizes the input context (no-op)
    - produces a small, deterministic plan (no LLM planner yet)
    - performs per-sub-task retrieval using the provided ``Embedder`` and
      ``VectorStore``
    - returns a clearly marked placeholder answer (reasoning and verification
      remain stubs in this phase)

    This function is safe to call but is not wired into the main analysis
    pipeline yet, so it has no effect on existing behaviour.
    """

    normalized = _normalize_input(context)
    subtasks = _plan_subtasks(normalized)
    evidence = _retrieve_evidence(
        normalized,
        subtasks,
        embedder=embedder,
        vector_store=vector_store,
        top_k=top_k,
    )
    updated_management_plan_text, plan_issues = _reason_updated_management_plan(
        normalized,
        evidence,
        llm_client=llm_client,
    )

    debug_info: Dict[str, Any] = {
        "normalized_context": normalized,
        "subtasks": subtasks,
        "evidence_bundles": evidence,
        # Rationale: store new Part 3 output for debug UI consumption without
        # changing existing behaviour.
        "updated_management_plan_text": updated_management_plan_text,
    }

    return AgenticResult(
        updated_management_plan_text=updated_management_plan_text,
        plan_issues=plan_issues,
        used_chunks=[],
        warnings=[
            "agentic flow is in Phase 1 skeleton mode; no real planning/"
            "retrieval/reasoning has been applied",
        ],
        debug_info=debug_info,
    )
