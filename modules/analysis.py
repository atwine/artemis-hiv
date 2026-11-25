"""The visit analysis behind the "Save encounter" button, with no Streamlit in it.

`run_visit_analysis` takes a patient, today's note, a guideline search engine and an LLM
client, and returns an `AnalysisResult`. app.py builds the engine and the client, calls
this, and copies the result into the screen's session state. Tests call it directly.

Moved out of app.py's `_run_analysis` without changing behaviour (Phase 1, option B);
tests/test_pipeline_golden.py checks that. Phase 1 fixes change it from here, each with
its own test.
"""

from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from modules.agentic_flow import QueryContext, run_agentic_flow
from modules.alert_rules import Alert, run_alerts
from modules.explanation_generator import (
    ExplanationResult,
    generate_audit_checklist_alerts,
    generate_explanation,
    generate_stage3_synthesis_issues,
)
from modules.llm_screening import generate_llm_screening_alerts
from modules.patient_parser import build_patient_context
from modules.rag_engine import RagEngine
from modules.stage1_summary import build_stage1_summary
from modules.vector_store import VectorSearchResult

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
    index_max_pages: Optional[int] = None
    retrieval_page_range: Optional[tuple[int, int]] = None
    use_llm: bool = True
    llm_mode: str = "LLM screening (generate alerts)"
    agentic: bool = False


@dataclass
class AnalysisResult:
    patient_id: Optional[str]
    alerts: List[Alert]
    results: List[Dict[str, Any]]
    status: str
    deterministic_alerts: List[Alert]
    evidence_map: Dict[str, List[VectorSearchResult]]
    screening_ran: bool
    screening_debug: Optional[Dict[str, Any]]
    patient_facts: Optional[Dict[str, Any]]
    agentic_enabled: bool
    agentic_result: Any
    agentic_reasoner: Optional[Dict[str, Any]]
    llm_error: Optional[str]
    llm_model: Optional[str]
    explain_seconds: Dict[str, float] = field(default_factory=dict)


def extract_patient_facts_from_history(notes_text: str) -> Dict[str, Any]:
    # Rationale: deterministic, lightweight extraction so clinicians can see what the system
    # believes is present in the free-text history even when no alerts are generated.
    text = (notes_text or "").strip()
    low = text.lower()

    # Rationale: match common ART abbreviations and full names to reduce false "empty" fact extraction.
    # This does not change alert logic; it only improves audit transparency.
    arv_terms = {
        "tdf": "TDF",
        "tenofovir": "TDF",
        "3tc": "3TC",
        "lamivudine": "3TC",
        "dtg": "DTG",
        "dolutegravir": "DTG",
        "azt": "AZT",
        "zidovudine": "AZT",
        "ftc": "FTC",
        "emtricitabine": "FTC",
        "efv": "EFV",
        "efavirenz": "EFV",
        "nvp": "NVP",
        "nevirapine": "NVP",
        "d4t": "D4T",
        "stavudine": "D4T",
        "abc": "ABC",
        "abacavir": "ABC",
        "taf": "TAF",
    }
    meds_norm = set()
    for term, canon in arv_terms.items():
        if re.search(rf"\b{re.escape(term)}\b", low):
            meds_norm.add(canon)
    meds_found = sorted(meds_norm)

    symptom_terms = [
        "bone pain",
        "fracture",
        "difficulty walking",
        "proximal muscle weakness",
        "weakness",
        "fatigue",
        "dizziness",
    ]
    symptoms_found = [t for t in symptom_terms if t in low]

    key_line_terms = [
        "current art",
        "viral load",
        "cd4",
        "serum creatinine",
        "creatinine",
        "egfr",
        "urinalysis",
        "phosphate",
        "alp",
        "vitamin d",
        "dexa",
        "t-score",
        "looser",
    ]
    key_lines: List[str] = []
    for ln in (text.splitlines() or []):
        s = ln.strip()
        if not s:
            continue
        sl = s.lower()
        if any(term in sl for term in key_line_terms):
            key_lines.append(s)

    # Bound the output so it remains readable in the UI.
    return {
        # Rationale: include minimal diagnostics so a clinician can confirm what text was actually checked.
        "notes_text_char_count": len(text),
        "notes_text_preview": (text[:300] + ("…" if len(text) > 300 else "")),
        "medications_detected": meds_found,
        "symptoms_detected": symptoms_found,
        "key_history_lines": key_lines[:25],
    }


def compute_overall_status(alerts: List[Alert]) -> str:
    if not alerts:
        return "GREEN"

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


def _in_page_range(
    results: List[VectorSearchResult], page_range: Optional[tuple[int, int]]
) -> List[VectorSearchResult]:
    # Client-side guard: enforce page-range bounds post-retrieval to avoid any caching/store drift.
    if page_range is None:
        return results
    lo, hi = page_range
    return [
        r
        for r in results
        if (
            r.metadata.get("page_number") is not None
            and int(r.metadata.get("page_number")) >= int(lo)
            and int(r.metadata.get("page_number")) <= int(hi)
        )
    ]


def _retrieve(
    rag: RagEngine, *, context: Any, alert: Alert, top_k: int, page_range: Optional[tuple[int, int]]
) -> List[VectorSearchResult]:
    # Rationale: compatibility — during hot-reload, a cached RagEngine may not yet
    # accept the new page_range kw. Try new signature first, then fall back.
    try:
        found = rag.retrieve_for_alert(patient_context=context, alert=alert, top_k=top_k, page_range=page_range)
    except (TypeError, ValueError):
        found = rag.retrieve_for_alert(patient_context=context, alert=alert, top_k=top_k)
    return _in_page_range(found, page_range)


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
    llm_mode = options.llm_mode
    top_k = options.top_k
    retrieval_page_range = options.retrieval_page_range

    def status(label: str, state: str) -> None:
        if on_status is not None:
            on_status(label, state)

    patient_copy = copy.deepcopy(patient)
    patient_copy.setdefault("today_encounter", {})
    patient_copy["today_encounter"]["note"] = today_note

    context = build_patient_context(patient_copy)
    alerts = run_alerts(context)
    # Preserve Stage 1 deterministic alerts for Stage 3 synthesis input.
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
                metadata={
                    "llm_mode": llm_mode,
                    "top_k": top_k,
                    "index_max_pages": options.index_max_pages,
                    "retrieval_page_range": retrieval_page_range,
                },
            )
            agentic_result = run_agentic_flow(
                agentic_context,
                embedder=rag._embedder,
                vector_store=rag._vector_store,
                top_k=top_k,
                page_range=retrieval_page_range,
                llm_client=llm_client,
            )
        except Exception as exc:
            agentic_result = {"error": str(exc), "type": exc.__class__.__name__}

    llm_error: Optional[str] = None

    # Rationale: LLM-first audit checklist layer (Option B) - checklist items are
    # represented as Alert objects and must be acknowledged/overridden before Finalize.
    checklist_seed = Alert(
        alert_id="llm_checklist_seed",
        title="Guideline audit checklist",
        message="LLM audit checklist seed",
        evidence={"type": "llm_audit_checklist_seed"},
        query_hint="visit audit checklist labs monitoring regimen",
    )
    checklist_retrieved = _retrieve(
        rag, context=context, alert=checklist_seed, top_k=top_k, page_range=retrieval_page_range
    )

    if use_llm:
        # Rationale: the first LLM call is a good proxy for "Ollama connected".
        status(f"{llm_name}: generating audit checklist…", "running")
    # Manage LLM calls by mode: checklist vs per‑alert explanations vs synthesis vs screening.
    # In Synthesis mode, skip the checklist LLM to keep a single LLM call later.
    checklist_llm = llm_client if (use_llm and llm_mode == "Checklist only") else None
    explanation_llm = llm_client if (use_llm and llm_mode == "Per-alert explanations") else None

    if llm_mode == "Checklist only":
        if use_llm and checklist_llm is not None:
            status(f"{llm_name}: generating audit checklist…", "running")
        checklist_alerts = generate_audit_checklist_alerts(
            patient_context=context,
            retrieved_chunks=checklist_retrieved,
            llm_client=checklist_llm,
        )
        if use_llm and checklist_llm is not None:
            last_err = checklist_llm.last_error if checklist_llm is not None else None
            if last_err:
                status(f"{llm_name} error: {last_err}", "error")
            else:
                status(f"{llm_name} connected (response received)", "complete")
        if checklist_alerts:
            alerts = list(alerts) + checklist_alerts

    # Optional: LLM-first screening mode — generate alerts directly from Stage 1 summary
    # and checklist evidence. Deterministic alerts remain the fallback when
    # screening fails (error or unparseable output).
    screening_ran = False
    screening_debug: Optional[Dict[str, Any]] = None
    patient_facts: Optional[Dict[str, Any]] = None
    if use_llm and llm_mode == "LLM screening (generate alerts)" and llm_client is not None:
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
        # Rationale: persist screening audit inputs/parse status for GREEN "no alerts" explanation.
        patient_facts = extract_patient_facts_from_history(context.notes_text)

        parse_status = (screening_debug.get("parse_status") or "").strip().lower()
        last_err = llm_client.last_error
        screening_succeeded = last_err is None and parse_status in {"parsed_empty", "parsed_nonempty"}

        if screening_succeeded:
            alerts = list(screening_alerts)
            deterministic_alerts = []

        if last_err:
            status(f"{llm_name} error: {last_err}", "error")
        else:
            status(f"{llm_name} connected (response received)", "complete")
        if llm_error is None:
            llm_error = last_err

    results: List[Dict[str, Any]] = []
    # Evidence map for Stage 3 synthesis (per deterministic alert).
    evidence_map: Dict[str, List[VectorSearchResult]] = {}
    explain_seconds: Dict[str, float] = {}

    for alert in alerts:
        if (alert.evidence or {}).get("type") == "llm_audit_checklist":
            # Rationale: checklist alerts already contain LLM-produced guidance and
            # citations; avoid additional LLM calls per checklist item.
            retrieved: List[VectorSearchResult] = []
            explanation = ExplanationResult(text=alert.message, used_chunks=[], used_llm=False)
        else:
            retrieved = _retrieve(rag, context=context, alert=alert, top_k=top_k, page_range=retrieval_page_range)
            # Capture evidence for Stage 3 only for deterministic (non-LLM) alerts.
            evidence_map[alert.alert_id] = list(retrieved)

            if use_llm and explanation_llm is not None:
                # Rationale: per-alert LLM calls may each take time; show which step is active.
                status(f"{llm_name}: generating explanation for '{alert.title}'…", "running")
            # Rationale: measure per‑alert LLM explanation time to track latency and surface it in the UI.
            _t0 = time.perf_counter()
            explanation = generate_explanation(
                patient_context=context,
                alert=alert,
                retrieved_chunks=retrieved,
                llm_client=explanation_llm,
            )
            _t1 = time.perf_counter()
            explain_seconds[alert.alert_id] = max(0.0, float(_t1 - _t0))

            if use_llm and explanation_llm is not None:
                last_err = explanation_llm.last_error if explanation_llm is not None else None
                if last_err:
                    status(f"{llm_name} error: {last_err}", "error")
                else:
                    status(f"{llm_name} connected (response received)", "complete")

        # Rationale: capture the first LLM failure reason so the UI can show why
        # it fell back to deterministic mode.
        if explanation_llm is not None and not explanation.used_llm:
            last_err = explanation_llm.last_error
            if last_err and llm_error is None:
                llm_error = last_err

        results.append({"alert": alert, "retrieved": retrieved, "explanation": explanation})

    # Stage 3 synthesis: single LLM call producing structured issues as new Alerts.
    if use_llm and llm_mode == "Synthesis" and llm_client is not None:
        status(f"{llm_name}: generating synthesis issues…", "running")
        try:
            synth_alerts = generate_stage3_synthesis_issues(
                patient_context=context,
                deterministic_alerts=deterministic_alerts,
                evidence_map=evidence_map,
                llm_client=llm_client,
            )
        except Exception:
            synth_alerts = []
        if synth_alerts:
            for a in synth_alerts:
                results.append(
                    {
                        "alert": a,
                        "retrieved": [],
                        "explanation": ExplanationResult(text=a.message, used_chunks=[], used_llm=False),
                    }
                )
            alerts = list(alerts) + synth_alerts

        last_err = llm_client.last_error
        if last_err:
            status(f"{llm_name} error: {last_err}", "error")
        else:
            status(f"{llm_name} connected (response received)", "complete")
        # Capture first error if no LLM text returned.
        if llm_error is None:
            llm_error = llm_client.last_error

    overall = compute_overall_status(alerts)
    client_used = checklist_llm or explanation_llm

    agentic_reasoner = None
    if options.agentic:
        try:
            agentic_reasoner = {
                "final_status": overall,
                "final_alert_count": len(alerts),
                "deterministic_alert_ids": [a.alert_id for a in deterministic_alerts],
                "final_alert_ids": [a.alert_id for a in alerts],
                "evidence_map_keys": list(evidence_map.keys()),
                "agentic_result_present": agentic_result is not None,
            }
        except Exception as exc:
            agentic_reasoner = {"error": str(exc), "type": exc.__class__.__name__}

    return AnalysisResult(
        patient_id=patient.get("patient_id"),
        alerts=alerts,
        results=results,
        status=overall,
        deterministic_alerts=deterministic_alerts,
        evidence_map=evidence_map,
        screening_ran=screening_ran,
        screening_debug=screening_debug,
        patient_facts=patient_facts,
        agentic_enabled=options.agentic,
        agentic_result=agentic_result,
        agentic_reasoner=agentic_reasoner,
        llm_error=llm_error,
        llm_model=client_used.model if client_used is not None else None,
        explain_seconds=explain_seconds,
    )
