from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import json
import logging

from artemis.rules.checks import Alert
from artemis.ai.client import ChatMessage, OllamaClient
from artemis.plan.plan_json import closing_index, strip_code_fences
from artemis.patient.record import PatientContext
from artemis.guidelines.vector_store import VectorSearchResult

logger = logging.getLogger(__name__)


def _build_screening_bundle(chunks: List[VectorSearchResult]) -> List[Dict[str, Any]]:
    bundle: List[Dict[str, Any]] = []
    for r in list(chunks or [])[:10]:
        bundle.append(
            {
                "chunk_id": r.chunk_id,
                "page_number": r.metadata.get("page_number"),
                "quote": (r.document or "")[:480],
            }
        )
    return bundle


SEVERITIES = ("critical", "high", "moderate", "low")
NO_SEVERITY = "not given"


def _is_alert(item: Any) -> bool:
    return isinstance(item, dict) and any(k in item for k in ("alert_id", "title", "message"))


def _read_list(raw: str, pos: int) -> Tuple[List[Any], str]:
    """Read list items one at a time from just after a "[".

    Returns the items read and how the list ended: "closed" (reached "]"), "cut" (the
    text ended first) or "broken" (an item could not be read; the items before it are kept).
    """
    decoder = json.JSONDecoder()
    items: List[Any] = []
    while True:
        while pos < len(raw) and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(raw):
            return items, "cut"
        if raw[pos] == "]":
            return items, "closed"
        try:
            value, pos = decoder.raw_decode(raw, pos)
        except json.JSONDecodeError:
            return items, ("broken" if closing_index(raw, pos) is not None else "cut")
        items.append(value)


def read_alert_list(text: str, *, finish_reason: Optional[str] = None) -> Tuple[List[Dict[str, Any]], str]:
    """Find the list of alerts in the model's reply (fix 8).

    The list may come after other words, including bracketed ones such as "[1]", or as
    a single alert object. Returns (alerts, status):
    - parsed_nonempty / parsed_empty: the list was read in full.
    - cut_off: the reply stopped part-way (the server said so, or the list never closed);
      the complete alerts before the cut are kept.
    - partly_read: some items in the list could not be read as alerts; the rest are kept.
    - parse_failed: no list of alerts was found.
    """
    raw = strip_code_fences(text or "")
    decoder = json.JSONDecoder()
    found: Optional[Tuple[List[Any], str]] = None
    ended_mid_list = False
    for i, ch in enumerate(raw):
        if ch == "[":
            items, end = _read_list(raw, i + 1)
            if any(_is_alert(x) for x in items) or (end == "closed" and not items):
                found = (items, end)
                break
            ended_mid_list = ended_mid_list or end == "cut"
        elif ch == "{":
            try:
                value, _ = decoder.raw_decode(raw, i)
            except json.JSONDecodeError:
                continue
            if _is_alert(value):
                found = ([value], "closed")
                break
    if found is None:
        cut = finish_reason == "length" or ended_mid_list
        return [], ("cut_off" if cut else "parse_failed")

    items, end = found
    alerts = [x for x in items if isinstance(x, dict)]
    if end == "cut" or finish_reason == "length":
        status = "cut_off"
    elif end == "broken" or len(alerts) < len(items):
        status = "partly_read"
    else:
        status = "parsed_nonempty" if alerts else "parsed_empty"
    return alerts, status


def _severity(value: Any) -> str:
    """One of the four severities, or "not given" when it is missing or something else (fix 8)."""
    s = str(value or "").strip().lower()
    return s if s in SEVERITIES else NO_SEVERITY


def _marked_citations(value: Any, shown_ids: set) -> List[Dict[str, Any]]:
    """The AI's citations, each marked with whether the AI was actually shown that passage."""
    raw_list = value if isinstance(value, list) else ([value] if value else [])
    out: List[Dict[str, Any]] = []
    for c in raw_list:
        c = dict(c) if isinstance(c, dict) else {"chunk_id": str(c)}
        c["shown_to_ai"] = str(c.get("chunk_id") or "") in shown_ids
        out.append(c)
    return out


def _as_written(patient_context: PatientContext) -> str:
    """The regimen as the clinician wrote it, when it says more than the drug codes."""
    written = (getattr(patient_context, "art_regimen_as_entered", "") or "").strip()
    codes = ", ".join(patient_context.art_regimen_current or [])
    return f" (as written: {written})" if written and written != codes else ""


def patient_facts(patient_context: PatientContext, stage1_summary: Dict[str, Any]) -> str:
    """Everything the AI is told about the patient: regimen, other medicines, every dated note,
    every dated lab and the summary. The screening and the guideline questions (Phase 2B fix 5q)
    both read this, so the question writer sees what the screening sees."""
    return (
        f"Patient ID: {patient_context.patient_id}\n"
        f"Age: {patient_context.age_years if patient_context.age_years is not None else 'Not recorded'} years\n"
        f"Sex: {patient_context.sex if patient_context.sex else 'Not recorded'}\n"
        f"Encounter date: {patient_context.encounter_date.isoformat()}\n\n"
        f"Current ART regimen: {', '.join(patient_context.art_regimen_current) if patient_context.art_regimen_current else 'None'}"
        f"{_as_written(patient_context)}\n"
        f"Other medications: {', '.join(patient_context.other_medications) if patient_context.other_medications else 'None'}\n\n"
        "Clinical notes, oldest first:\n"
        f"{patient_context.dated_notes}\n\n"
        "Laboratory results (age counted from the visit date):\n"
        f"{patient_context.lab_section}\n\n"
        "Stage 1 summary JSON:\n"
        f"{json.dumps(stage1_summary, ensure_ascii=False)}"
    )


def generate_llm_screening_alerts(
    *,
    patient_context: PatientContext,
    stage1_summary: Dict[str, Any],
    screening_chunks: List[VectorSearchResult],
    llm_client: Optional[OllamaClient],
    debug: Optional[Dict[str, Any]] = None,
) -> List[Alert]:
    if llm_client is None:
        if debug is not None:
            # Rationale: enable the UI to explain that screening could not run.
            debug["parse_status"] = "llm_unavailable"
        return []

    bundle = _build_screening_bundle(screening_chunks)
    shown_chunk_ids = [str(c["chunk_id"]) for c in bundle]

    # Rationale: enforce valid JSON output to avoid parse failures in the UI.
    # Ollama supports structured outputs via the `format` parameter (json or JSON schema). [src]
    # - https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
    output_schema: Dict[str, Any] = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "alert_id": {"type": "string"},
                "title": {"type": "string"},
                "message": {"type": "string"},
                "issue_type": {"type": "string"},
                "severity": {"type": "string", "enum": list(SEVERITIES)},
                "recommended_action": {"type": "string"},
                "citations": {
                    "type": "array",
                    # Only the passages the AI was shown can be cited; with none shown, nothing can.
                    # A server that follows the format can't produce an invented or placeholder
                    # citation such as "information_gap" (Phase 2, step 6).
                    **({} if shown_chunk_ids else {"maxItems": 0}),
                    "items": {
                        "type": "object",
                        "properties": {
                            "page_number": {"type": "integer"},
                            "chunk_id": {"type": "string", **({"enum": shown_chunk_ids} if shown_chunk_ids else {})},
                        },
                        "required": ["page_number", "chunk_id"],
                        "additionalProperties": True,
                    },
                },
            },
            "required": [
                "alert_id",
                "title",
                "message",
                "issue_type",
                "severity",
                "recommended_action",
                "citations",
            ],
            "additionalProperties": True,
        },
    }

    # system: ChatMessage = {
    #     "role": "system",
    #     "content": (
    #         "You are a clinical decision support system for HIV medication safety. "
    #         "Use the patient summary and guideline excerpts to screen for safety issues, monitoring gaps, toxicities, and drug–drug or drug–disease interactions. "
    #         "Pay particular attention to: (1) severe anemia (e.g., Hb < 8 g/dL) especially in patients on zidovudine/AZT or with chronic blood loss such as heavy menses/menorrhagia; "
    #         "(2) ART toxicities; (3) missing or overdue safety labs; and (4) guideline-recommended monitoring that has not been done. "
    #         "Return ONLY a JSON array of issues. Each issue must include: "
    #         "alert_id, title, message, issue_type, severity, recommended_action, and citations (list of objects with page_number and chunk_id)."
    #     ),
    # }

    # Rationale: ARTEMIS v3 prompt — redesigned for 4B quantized models.
    # Key design principles for small models:
    #   1. SHORT (~600 words vs ~1500 in v2) — small models lose track after ~500 words
    #   2. FLAT structure — no deep nesting, numbered lists only
    #   3. EXAMPLE-ANCHORED — one concrete example alert to guide format
    #   4. END-WEIGHTED — most critical rules at the end (small models attend to end)
    #   5. NO internal reasoning chains — just describe the desired output
    # All clinical screening requirements preserved: toxicity, interactions,
    # monitoring gaps, differential diagnosis, severity, citations.
    system: ChatMessage = {
        "role": "system",
        "content": """You are ARTEMIS, an HIV medication safety screening system. You receive a patient summary, guideline excerpts (with page_number and chunk_id), and optionally a clinician plan. You output ONLY a JSON array of safety alerts.

WHAT TO SCREEN FOR:
1. Drug toxicities — check if any lab abnormality or symptom could be caused by a current medication. Consider non-drug causes too (infection, dehydration, comorbidity). Present evidence for AND against drug attribution.
2. Drug interactions — between current medications, and between drugs and conditions (renal impairment, pregnancy, TB co-treatment).
3. Monitoring gaps — required labs or tests that are missing, overdue, or not in the clinician's plan.
4. Lab trends — a steadily worsening value (e.g., creatinine rising from 0.9 to 1.4 over years) is a problem even if the latest value alone seems acceptable.
5. Plan problems — anything in the clinician's plan that conflicts with guidelines, or guideline actions missing from the plan.
6. Compounding risks — drug + abnormal lab + comorbidity together may be dangerous even if each factor alone is not.

RULES:
- Only cite page_number and chunk_id values that appear in the provided excerpts. Never invent citations.
- Only state guideline rules that the excerpts support. Do not invent thresholds or contraindications.
- If no excerpt supports an alert, leave citations as an empty list []. Put nothing in citations except a chunk_id from the excerpts.
- Merge related excerpts: if 3 excerpts discuss the same topic, write ONE synthesized statement and list all citations.

SEVERITY:
- critical: "contraindicated", "do not use", "discontinue immediately"
- high: "avoid", "switch", "significant risk", substantial harm
- moderate: "caution", "monitor", "consider"
- low: optimisation / best practice

OUTPUT FORMAT — return ONLY a JSON array:
[
  {
    "alert_id": "unique_string",
    "title": "Short title, max 15 words",
    "message": "Max 150 words. State the guideline rule, then patient findings, then for toxicity alerts: evidence for and against drug attribution. Each sentence must add new information.",
    "issue_type": "medication_safety|monitoring_gap|toxicity|drug_interaction|guideline_deviation|plan_review|plan_add|information_gap",
    "severity": "critical|high|moderate|low",
    "recommended_action": "Specific guideline-based action, max 40 words",
    "citations": [{"page_number": <the excerpt's page_number>, "chunk_id": "<the excerpt's chunk_id>"}]
  }
]

EXAMPLE ALERT (use real data and real chunk_ids from the excerpts, not these placeholder values):
{"alert_id": "EXAMPLE_001", "title": "Example Drug Side Effect", "message": "Guidelines state X. Patient shows Y. Drug A is a known cause. However, non-drug cause B should also be considered.", "issue_type": "toxicity", "severity": "high", "recommended_action": "Specific action from the guideline excerpts.", "citations": [{"page_number": 99, "chunk_id": "use_real_chunk_id_from_excerpts"}]}

HARD LIMITS — FOLLOW STRICTLY:
- Maximum 5 alerts total. If you find more than 5 issues, keep only the most clinically important ones.
- If two issues are closely related (e.g., weight gain and obesity, or two aspects of the same drug toxicity), merge them into ONE alert. Do NOT create separate alerts for the same clinical concept.
- Each message: maximum 150 words. Each recommended_action: maximum 40 words.
- NEVER repeat the same point within an alert. Every sentence must add NEW information.
- If you have said something once, do NOT say it again. Stop writing that alert and move to the next one.
- Each alert_id must be unique. Never use the same alert_id twice.
- Return [] if no issues found.
""",
    }
    

    user: ChatMessage = {
        "role": "user",
        "content": (
            f"{patient_facts(patient_context, stage1_summary)}\n\n"
            "Guideline evidence excerpts (screening bundle):\n"
            f"{json.dumps(bundle, ensure_ascii=False)}\n\n"
            "Now output ONLY a JSON array of issues as described, or an empty array if there are no clinically relevant issues."
        ),
    }

    # Rationale: Ollama parameters tuned for 4B quantized model (MedGemma Q4_K_S).
    # - num_predict=1600: enough for ~5 detailed alerts without truncation.
    #   1200 caused truncation on complex patients with 5+ alerts (parse_failed).
    # - repeat_penalty=1.5: strong penalty on recently used tokens to break loops.
    #   [src] https://docs.ollama.com/modelfile — values >1.0 penalize repeated tokens.
    # - repeat_last_n=256: look-back window for repeat penalty. Default is 64 tokens
    #   (~50 words), which is too short to catch phrase-level loops. 256 tokens (~200
    #   words) covers the full length of a typical alert message.
    #   [src] https://docs.ollama.com/modelfile — repeat_last_n controls the window.
    llm_text = llm_client.chat(
        [system, user],
        format=output_schema,
        options_override={
            "num_predict": 1600,
            "repeat_penalty": 1.5,
            "repeat_last_n": 256,
        },
    )
    finish_reason = getattr(llm_client, "last_finish_reason", None)
    issues, parse_status = read_alert_list(llm_text or "", finish_reason=finish_reason)
    if debug is not None:
        # Rationale: persist the exact inputs/outputs used for screening so GREEN results
        # can explain what was checked and whether parsing succeeded.
        debug["raw_output"] = llm_text
        debug["screening_bundle"] = bundle
        debug["parse_status"] = parse_status
        debug["finish_reason"] = finish_reason
        debug["client_note"] = getattr(llm_client, "last_note", None)

    shown_ids = {str(c.get("chunk_id")) for c in bundle}
    alerts: List[Alert] = []
    kept: List[Dict[str, Any]] = []
    used_ids: set = set()
    for idx, issue in enumerate(issues):
        # Only exact repeats are dropped; different alerts with similar titles both stay (fix 8).
        if issue in kept:
            continue
        kept.append(issue)
        alert_id = str(issue.get("alert_id") or "").strip() or f"llm_screening_{idx}"
        base, n = alert_id, 1
        while alert_id in used_ids:
            n += 1
            alert_id = f"{base}-{n}"
        used_ids.add(alert_id)

        evidence: Dict[str, Any] = {
            "type": "llm_screening",
            "issue_type": str(issue.get("issue_type") or "screening_issue"),
            "severity": _severity(issue.get("severity")),
            "recommended_action": str(issue.get("recommended_action") or "").strip(),
            "citations": _marked_citations(issue.get("citations"), shown_ids),
            "raw_issue": issue,
        }
        alerts.append(
            Alert(
                alert_id=alert_id,
                title=str(issue.get("title") or "").strip() or "AI alert with no title",
                message=str(issue.get("message") or "").strip() or "The AI gave no explanation for this alert.",
                evidence=evidence,
                query_hint="HIV regimen safety monitoring toxicities drug interactions",
                source="ai",
            )
        )
    if debug is not None:
        debug["exact_repeats_dropped"] = len(issues) - len(kept)
    return alerts
