"""The visit analysis behind the "Save encounter" button, with no Streamlit in it.

`run_visit_analysis` takes a patient, today's note, a guideline search engine and an LLM
client, and returns an `AnalysisResult`. app.py builds the engine and the client, calls
this, and copies the result into the screen's session state. Tests call it directly.

Moved out of app.py's `_run_analysis` without changing behaviour (Phase 1, option B), and
from modules/analysis.py to here in fix 3. tests/test_pipeline_golden.py checks its output;
Phase 1 fixes change it from here, each with its own test.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Optional

from artemis.plan.flow import QueryContext, run_agentic_flow
from artemis.rules.checks import Alert, run_alerts
from modules.explanation_generator import generate_explanation
from artemis.ai.screening import generate_llm_screening_alerts, patient_facts
from artemis.ai.search_questions import ask_search_questions
from artemis.patient.record import build_patient_context

logger = logging.getLogger(__name__)
from modules.rag_engine import RagEngine
from artemis.patient.summary import build_stage1_summary
from artemis.guidelines.vector_store import VectorSearchResult

StatusCallback = Callable[[str, str], None]  # (label, state)

AGENTIC_QUESTION = (
    "Review this patient's symptoms, examination findings, "
    "and lab results (including trends over time). Could any "
    "of them be signs of drug toxicity from their current or "
    "past ART medications or co-medications? If so, what "
    "tests confirm it, and does the doctor's current plan "
    "adequately address the issue per Uganda HIV guidelines?"
)


@dataclass
class AnalysisOptions:
    top_k: int = 5
    use_llm: bool = True
    agentic: bool = False


# Every way the AI review can end, and every overall status, now in artemis/statuses.py (a file
# with no heavy imports); re-exported here so `from artemis.visit import STATUSES` keeps working.
from artemis.statuses import AI_REVIEW_OUTCOMES, STATUSES, status_name  # noqa: E402,F401


@dataclass
class AnalysisResult:
    patient_id: Optional[str]
    alerts: List[Alert]
    results: List[Dict[str, Any]]
    status: str
    # What happened to the AI review: "not_run" (switched off), "ok", "failed" (no reply),
    # "unreadable" (a reply that could not be read as a list of alerts), the partial "cut_off" and
    # "partly_read", or "search_unavailable" (the search model did not load, so it did not run; G33).
    screening_outcome: str
    screening_ran: bool
    screening_debug: Optional[Dict[str, Any]]
    # The recorded-facts summary the AI review read (fix 6); shown when nothing was found (fix 10).
    patient_summary: Optional[Dict[str, Any]]
    agentic_enabled: bool
    agentic_result: Any
    agentic_reasoner: Optional[Dict[str, Any]]
    llm_error: Optional[str]

    def __post_init__(self) -> None:
        if self.screening_outcome not in AI_REVIEW_OUTCOMES:
            raise ValueError(f"unknown AI review result {self.screening_outcome!r}: add it to AI_REVIEW_OUTCOMES "
                             "and to docs/screen-checklist.md")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}: add it to STATUSES and to docs/screen-checklist.md")


def compute_overall_status(alerts: List[Alert], screening_outcome: str = "ok") -> str:
    """GREEN, AMBER or RED from the alerts; INCOMPLETE when nothing was found but the AI review
    did not finish cleanly (failed, unreadable, cut off or partly read)."""
    if not alerts:
        return "GREEN" if screening_outcome in {"ok", "not_run"} else "INCOMPLETE"

    # Rationale: if severity is available (e.g., from LLM screening issues), use the
    # worst severity to drive the overall status colour. Deterministic alerts that
    # do not specify a severity are treated as at least moderate.
    severity_rank = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
    max_rank = 1  # default to "moderate" when any alert exists but no severity set
    for alert in alerts:
        evidence = alert.evidence or {}
        sev = str(evidence.get("severity") or "").lower()
        rank = severity_rank.get(sev, max_rank)
        if rank > max_rank:
            max_rank = rank

    if max_rank >= 2:
        return "RED"
    return "AMBER"


def _retrieve(rag: RagEngine, *, context: Any, alert: Alert, top_k: int) -> List[VectorSearchResult]:
    return rag.retrieve_for_alert(patient_context=context, alert=alert, top_k=top_k)


def _with_note(patient: Dict[str, Any], today_note: str) -> Dict[str, Any]:
    patient_copy = copy.deepcopy(patient)
    patient_copy.setdefault("today_encounter", {})
    patient_copy["today_encounter"]["note"] = today_note
    return patient_copy


def patient_context_for(patient: Dict[str, Any], today_note: str) -> Any:
    """The patient context the analysis searches with: the record, with today's note."""
    return build_patient_context(_with_note(patient, today_note))


def patient_summary_for(patient: Dict[str, Any], today_note: str) -> Dict[str, Any]:
    """The recorded-facts summary the AI reads, as the analysis builds it."""
    patient_copy = _with_note(patient, today_note)
    return build_stage1_summary(patient=patient_copy, context=build_patient_context(patient_copy))


# Shown when the search model did not load and the AI review is off (G33).
SEARCH_UNAVAILABLE = ("Guideline search is unavailable (the search model did not load), "
                      "so the AI review is off for this visit")
QUESTION_PASSAGES = 2  # passages taken for each of the AI's questions
SCREENING_MAX = 10  # passages the AI screening reads at most


def merge_by_turns(result_lists: List[List[Any]], limit: int) -> List[Any]:
    """Each search's best passage first, then each one's second, and so on, without repeats."""
    merged: List[Any] = []
    seen: set = set()
    for rank in range(max((len(r) for r in result_lists), default=0)):
        for results in result_lists:
            if rank < len(results) and results[rank].chunk_id not in seen:
                seen.add(results[rank].chunk_id)
                merged.append(results[rank])
    return merged[:limit]


@dataclass
class ScreeningSearch:
    passages: List[VectorSearchResult]  # what the AI screening reads
    questions: List[str]  # the AI's own guideline questions; empty when the generic search ran


def screening_search(rag: RagEngine, context: Any, top_k: int, *, llm_client: Any = None,
                     summary: Optional[Dict[str, Any]] = None) -> ScreeningSearch:
    """The guideline passages the AI screening reads. With an AI, it first writes the patient's own
    guideline questions and each is searched (best 2 passages each, up to 10; Phase 2B fix 5q).
    Without one, or when its reply is unusable, one fixed query plus the patient's notes (G31).
    The search check calls this too, so it measures exactly what the app does. (Fix 5a, one
    templated search per drug, medicine, rule alert and symptom, was tried and dropped.)"""
    questions = (ask_search_questions(llm_client, patient_facts(context, summary))
                 if llm_client is not None and summary is not None else [])
    if questions:
        return ScreeningSearch(
            merge_by_turns([rag.search(q, top_k=QUESTION_PASSAGES) for q in questions], SCREENING_MAX), questions)
    checklist_seed = Alert(
        alert_id="llm_checklist_seed",
        title="Guideline audit checklist",
        message="LLM audit checklist seed",
        evidence={"type": "llm_audit_checklist_seed"},
        query_hint="visit audit checklist labs monitoring regimen",
    )
    return ScreeningSearch(_retrieve(rag, context=context, alert=checklist_seed, top_k=top_k), [])


def _cited_passages(alert: Alert, shown: List[VectorSearchResult]) -> List[VectorSearchResult]:
    """The passages an AI alert cited that the AI was actually shown, in citation order (fix 8)."""
    by_id = {r.chunk_id: r for r in shown}
    out: List[VectorSearchResult] = []
    for c in (alert.evidence or {}).get("citations") or []:
        # Only the first 10 passages go to the AI, so a later one can't count even if it was found.
        r = by_id.get(str(c.get("chunk_id") or "")) if c.get("shown_to_ai") else None
        if r is not None and r not in out:
            out.append(r)
    return out


def run_visit_analysis(
    *,
    patient: Dict[str, Any],
    today_note: str,
    rag: RagEngine,
    llm_client: Any,
    options: AnalysisOptions,
    llm_name: str = "LLM",
    on_status: Optional[StatusCallback] = None,
) -> AnalysisResult:
    # Rationale: keep analysis deterministic for alert triggering, and only use the
    # LLM for explanation/citation if available.
    use_llm = options.use_llm
    top_k = options.top_k

    def status(label: str, state: str) -> None:
        if on_status is not None:
            on_status(label, state)

    patient_copy = _with_note(patient, today_note)
    context = build_patient_context(patient_copy)
    alerts = run_alerts(context)
    # The fixed-rule alerts. They are always shown, next to any AI alerts (fix 3).
    deterministic_alerts = list(alerts)
    # Build Stage 1 summary once so it can be reused by LLM screening and narrative.
    stage1_summary = build_stage1_summary(patient=patient_copy, context=context)

    # Optional: agentic planner + per-subtask retrieval.
    agentic_result = None
    search_ready = rag.search_ready  # the plan step and the AI review both stop without it (G33)
    if options.agentic and search_ready:
        try:
            agentic_context = QueryContext(
                question_text=AGENTIC_QUESTION,
                patient_raw=patient_copy,
                patient_summary=stage1_summary,
                metadata={"top_k": top_k},
            )
            agentic_result = run_agentic_flow(
                agentic_context,
                embedder=rag._embedder,
                vector_store=rag._vector_store,
                top_k=top_k,
                llm_client=llm_client,
            )
        except Exception as exc:
            agentic_result = {"error": str(exc), "type": exc.__class__.__name__}

    llm_error: Optional[str] = None

    # With the search model not loaded, the AI review is switched off and the rule checks still
    # run (G33, owner's decision 2026-11-26): an alert built on near-random passages looks as sure
    # as a good one.
    ai_on = use_llm and llm_client is not None
    if not search_ready:
        logger.warning("Guideline search model did not load; AI review off for this visit")
        status(f"{SEARCH_UNAVAILABLE}. The rule checks still ran.", "error")
    elif ai_on:
        status(f"{llm_name}: listing guideline questions for this patient…", "running")
    found = (screening_search(rag, context, top_k, llm_client=llm_client if ai_on else None, summary=stage1_summary)
             if search_ready else ScreeningSearch([], []))
    checklist_retrieved = found.passages

    # Optional: LLM-first screening mode — generate alerts directly from Stage 1 summary
    # and checklist evidence. Deterministic alerts remain the fallback when
    # screening fails (error or unparseable output).
    screening_ran = False
    screening_outcome = "not_run"
    screening_debug: Optional[Dict[str, Any]] = None
    if not search_ready:
        screening_outcome = "search_unavailable"
    elif ai_on:
        screening_ran = True
        status(f"{llm_name}: screening for safety issues…", "running")
        screening_debug = {"search_questions": found.questions}
        screening_alerts = generate_llm_screening_alerts(
            patient_context=context,
            stage1_summary=stage1_summary,
            screening_chunks=checklist_retrieved,
            llm_client=llm_client,
            debug=screening_debug,
        )

        parse_status = (screening_debug.get("parse_status") or "").strip().lower()
        last_err = llm_client.last_error
        if last_err is not None:
            screening_outcome = "failed"
        elif parse_status in {"parsed_empty", "parsed_nonempty"}:
            screening_outcome = "ok"
        elif parse_status in {"cut_off", "partly_read"}:
            # The alerts read before the cut are kept; the banner says others may be missing (fix 8).
            screening_outcome = parse_status
        else:
            screening_outcome = "unreadable"
        if screening_outcome in {"ok", "cut_off", "partly_read"}:
            # Both kinds share one list and one set of review controls, keyed by id: an AI
            # alert never takes a rule alert's id (review finding, 1.Z).
            rule_ids = {a.alert_id for a in deterministic_alerts}
            screening_alerts = [
                replace(a, alert_id=f"{a.alert_id}-ai") if a.alert_id in rule_ids else a for a in screening_alerts
            ]
            alerts = list(deterministic_alerts) + list(screening_alerts)

        if last_err:
            # The details go to the log; the screen stays generic (review finding, 1.Z).
            logger.warning("AI review failed: %s", last_err)
            status(f"{llm_name}: the AI review failed (details in the app log)", "error")
        else:
            status(f"{llm_name} connected (response received)", "complete")
        if llm_error is None:
            llm_error = last_err

    results: List[Dict[str, Any]] = []
    for alert in alerts:
        # An AI alert's references are the passages it cited from those it was shown; a rule
        # alert's are found by a search for it (fix 8).
        if alert.source == "ai":
            retrieved = _cited_passages(alert, checklist_retrieved)
        elif not search_ready:
            retrieved = []
        else:
            retrieved = _retrieve(rag, context=context, alert=alert, top_k=top_k)
        explanation = generate_explanation(patient_context=context, alert=alert, retrieved_chunks=retrieved)
        results.append({"alert": alert, "retrieved": retrieved, "explanation": explanation})

    overall = compute_overall_status(alerts, screening_outcome)

    agentic_reasoner = None
    if options.agentic:
        agentic_reasoner = {
            "final_status": overall,
            "final_alert_count": len(alerts),
            "deterministic_alert_ids": [a.alert_id for a in deterministic_alerts],
            "final_alert_ids": [a.alert_id for a in alerts],
            "evidence_map_keys": [r["alert"].alert_id for r in results],
            "agentic_result_present": agentic_result is not None,
        }

    return AnalysisResult(
        patient_id=patient.get("patient_id"),
        alerts=alerts,
        results=results,
        status=overall,
        screening_outcome=screening_outcome,
        screening_ran=screening_ran,
        screening_debug=screening_debug,
        patient_summary=stage1_summary if screening_ran else None,
        agentic_enabled=options.agentic,
        agentic_result=agentic_result,
        agentic_reasoner=agentic_reasoner,
        llm_error=llm_error,
    )
