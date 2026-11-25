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
from artemis.ai.screening import generate_llm_screening_alerts
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


@dataclass
class AnalysisResult:
    patient_id: Optional[str]
    alerts: List[Alert]
    results: List[Dict[str, Any]]
    status: str
    deterministic_alerts: List[Alert]
    # What happened to the AI review: "not_run" (switched off), "ok", "failed" (no reply)
    # or "unreadable" (a reply that could not be read as a list of alerts).
    screening_outcome: str
    screening_ran: bool
    screening_debug: Optional[Dict[str, Any]]
    # The recorded-facts summary the AI review read (fix 6); shown when nothing was found (fix 10).
    patient_summary: Optional[Dict[str, Any]]
    agentic_enabled: bool
    agentic_result: Any
    agentic_reasoner: Optional[Dict[str, Any]]
    llm_error: Optional[str]


def compute_overall_status(alerts: List[Alert], screening_outcome: str = "ok") -> str:
    """GREEN, YELLOW or RED from the alerts; INCOMPLETE when nothing was found but the AI review
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
    return "YELLOW"


def _retrieve(rag: RagEngine, *, context: Any, alert: Alert, top_k: int) -> List[VectorSearchResult]:
    return rag.retrieve_for_alert(patient_context=context, alert=alert, top_k=top_k)


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

    patient_copy = copy.deepcopy(patient)
    patient_copy.setdefault("today_encounter", {})
    patient_copy["today_encounter"]["note"] = today_note

    context = build_patient_context(patient_copy)
    alerts = run_alerts(context)
    # The fixed-rule alerts. They are always shown, next to any AI alerts (fix 3).
    deterministic_alerts = list(alerts)
    # Build Stage 1 summary once so it can be reused by LLM screening and narrative.
    stage1_summary = build_stage1_summary(patient=patient_copy, context=context)

    # Optional: agentic planner + per-subtask retrieval.
    agentic_result = None
    if options.agentic:
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

    # The guideline passages the screening step reads come from this one fixed query
    # (a retrieval fault logged for Phase 2B).
    checklist_seed = Alert(
        alert_id="llm_checklist_seed",
        title="Guideline audit checklist",
        message="LLM audit checklist seed",
        evidence={"type": "llm_audit_checklist_seed"},
        query_hint="visit audit checklist labs monitoring regimen",
    )
    checklist_retrieved = _retrieve(rag, context=context, alert=checklist_seed, top_k=top_k)

    # Optional: LLM-first screening mode — generate alerts directly from Stage 1 summary
    # and checklist evidence. Deterministic alerts remain the fallback when
    # screening fails (error or unparseable output).
    screening_ran = False
    screening_outcome = "not_run"
    screening_debug: Optional[Dict[str, Any]] = None
    if use_llm and llm_client is not None:
        screening_ran = True
        status(f"{llm_name}: screening for safety issues…", "running")
        screening_debug = {}
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
        deterministic_alerts=deterministic_alerts,
        screening_outcome=screening_outcome,
        screening_ran=screening_ran,
        screening_debug=screening_debug,
        patient_summary=stage1_summary if screening_ran else None,
        agentic_enabled=options.agentic,
        agentic_result=agentic_result,
        agentic_reasoner=agentic_reasoner,
        llm_error=llm_error,
    )
