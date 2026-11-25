"""Deterministic alert rules.

This module is intentionally rule-based for demo reliability.
The LLM is used later for explanation/citation, not for deciding whether an alert triggers.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional

from artemis.patient.medicines import NSAIDS
from artemis.patient.record import PatientContext, days_since_lab

# A mention counts only if no negation comes before it in the same sentence:
# "No proteinuria", "denies NSAID use" and "negative for protein" are not findings.
_NEGATION = re.compile(r"\b(no|not|denies|denied|without|negative for|nil)\b[^.;\n]*$", re.IGNORECASE)


def _mentions(text: str, patterns: List[str]) -> List[str]:
    """The patterns (regular expressions) found in the text, skipping negated mentions."""
    hits: List[str] = []
    for pattern in patterns:
        for m in re.finditer(pattern, text or "", re.IGNORECASE):
            if not _NEGATION.search((text or "")[max(0, m.start() - 60) : m.start()]):
                hits.append(m.group(0).lower())
                break
    return hits


@dataclass(frozen=True)
class Alert:
    alert_id: str
    title: str
    message: str
    evidence: Dict[str, Any]
    query_hint: str
    # Where the alert came from: "rule" (the fixed checks in this file) or "ai" (AI screening).
    source: str = "rule"


def run_alerts(context: PatientContext) -> List[Alert]:
    """Run all deterministic checks and return a list of alerts."""

    alerts: List[Alert] = []

    tdf_alert = _check_tdf_creatinine_overdue(context)
    if tdf_alert is not None:
        alerts.append(tdf_alert)

    # Rationale: extra demo rules covering common real-world comorbidities/signals
    # often present in patient notes (e.g., Mr. K.S. sample case).
    nsaid_alert = _check_tdf_nsaid_use(context)
    if nsaid_alert is not None:
        alerts.append(nsaid_alert)

    proteinuria_alert = _check_possible_proteinuria(context)
    if proteinuria_alert is not None:
        alerts.append(proteinuria_alert)

    bp_alert = _check_suboptimal_bp_with_missed_amlodipine(context)
    if bp_alert is not None:
        alerts.append(bp_alert)

    efv_alert = _check_efv_sleep_disturbance(context)
    if efv_alert is not None:
        alerts.append(efv_alert)

    return alerts


def _check_tdf_creatinine_overdue(context: PatientContext) -> Optional[Alert]:
    """If on TDF, flag if creatinine is overdue.

    Threshold is set to 12 months for a conservative demo rule.
    """

    if "TDF" not in context.art_regimen_current:
        return None

    days = days_since_lab(context, "creatinine")
    if days is None and _mentions(context.labs_narrative or "", [r"creatinine"]):
        return Alert(
            alert_id="tdf_creatinine_pasted_only",
            title="Creatinine recorded only as pasted text",
            message=(
                "A creatinine result appears only in pasted lab text, so its date is unknown. "
                "Check when it was taken and enter it as a dated lab result for a patient on TDF."
            ),
            evidence={"regimen": context.art_regimen_current, "creatinine": "pasted text only"},
            query_hint="TDF creatinine monitoring frequency",
        )
    if days is None:
        return Alert(
            alert_id="tdf_creatinine_missing",
            title="Creatinine missing while on TDF",
            message="Consider ordering creatinine/eGFR monitoring for a patient on TDF; no recent creatinine result found in history.",
            evidence={
                "regimen": context.art_regimen_current,
                "creatinine": None,
            },
            query_hint="TDF creatinine monitoring frequency",
        )

    if days <= 365:
        return None

    return Alert(
        alert_id="tdf_creatinine_overdue",
        title="Creatinine monitoring overdue while on TDF",
        message=f"Creatinine last recorded {days} days ago for a patient on TDF. Consider ordering repeat renal function monitoring.",
        evidence={
            "regimen": context.art_regimen_current,
            "days_since_creatinine": days,
        },
        query_hint="TDF renal function monitoring creatinine schedule",
    )


def _check_efv_sleep_disturbance(context: PatientContext) -> Optional[Alert]:
    """If on EFV, flag if notes mention sleep disturbance terms."""

    if "EFV" not in context.art_regimen_current:
        return None

    hits = _mentions(
        context.notes_text,
        [
            r"insomnia",
            r"vivid dreams?",
            r"nightmares?",
            r"sleep disturbances?",
            r"(poor|bad|disturbed) sleep",
            r"(trouble|difficulty|problems?) sleeping",
            r"(can't|cannot|unable to) sleep",
            r"sleepless",
        ],
    )
    if not hits:
        return None

    return Alert(
        alert_id="efv_sleep_disturbance",
        title="Possible EFV neuropsychiatric side effects",
        message="Sleep disturbance mentioned in notes for a patient on EFV. Consider assessing EFV tolerance and reviewing guideline management options.",
        evidence={
            "regimen": context.art_regimen_current,
            "keyword_hits": hits,
        },
        query_hint="Efavirenz sleep disturbance vivid dreams management",
    )


def _check_tdf_nsaid_use(context: PatientContext) -> Optional[Alert]:
    """If on TDF, flag if notes mention common NSAID use.

    This is a conservative, text-based demo rule intended to surface potential renal
    risk factors that may not be captured as structured data.
    """

    if "TDF" not in context.art_regimen_current:
        return None

    text = "\n".join([context.notes_text or ""] + list(context.other_medications or []))
    hits = _mentions(text, [rf"{name}s?" for name in NSAIDS])
    if not hits:
        return None

    return Alert(
        alert_id="tdf_nsaid_use",
        title="NSAID use mentioned while on TDF",
        message="NSAID use is mentioned in notes for a patient on TDF. Consider reviewing renal risk and ensuring appropriate monitoring.",
        evidence={
            "regimen": context.art_regimen_current,
            "keyword_hits": hits,
        },
        query_hint="TDF NSAID renal risk monitoring",
    )


def _check_possible_proteinuria(context: PatientContext) -> Optional[Alert]:
    """Flag if notes mention proteinuria/protein on dipstick.

    Rationale: urinalysis is not yet modeled as structured labs in the demo schema.
    """

    text = "\n".join([context.notes_text or "", context.labs_narrative or ""])
    hits = _mentions(
        text,
        [r"proteinuria", r"trace protein", r"protein\s*[:=-]?\s*(trace|\d\s*\+|\+{1,3})"],
    )
    if not hits:
        return None

    return Alert(
        alert_id="possible_proteinuria",
        title="Proteinuria mentioned in notes",
        message="Proteinuria (or trace protein) is mentioned in notes. Consider follow-up assessment and management per local guidance.",
        evidence={
            "keyword_hits": hits,
        },
        query_hint="proteinuria dipstick trace protein evaluation",
    )


def _check_suboptimal_bp_with_missed_amlodipine(context: PatientContext) -> Optional[Alert]:
    """Flag if notes suggest suboptimal BP control with missed amlodipine doses."""

    text = (context.notes_text or "").lower()
    meds = " ".join(context.other_medications or []).lower()
    if "amlodipine" not in text and "amlodipine" not in meds:
        return None

    # Rationale: keep matching conservative to avoid false positives from generic
    # medication lists; require both a control concern and a missed-dose cue.
    control_terms = ["sub-optimally controlled", "suboptimally controlled", "bp is sub"]
    control_hits = [k for k in control_terms if k in text]
    missed_hits = [
        m.group(0)
        for m in re.finditer(r"\bmiss(ed|ing)\b[^.;\n]{0,40}\b(doses?|tablets?|pills?|amlodipine)\b", text)
    ]
    if not control_hits or not missed_hits:
        return None

    return Alert(
        alert_id="suboptimal_bp_missed_amlodipine",
        title="BP control concern with missed amlodipine doses",
        message="Notes suggest suboptimal BP control and missed amlodipine doses. Consider adherence counseling and BP follow-up.",
        evidence={
            "control_term_hits": control_hits,
            "missed_term_hits": missed_hits,
        },
        query_hint="hypertension suboptimal control missed amlodipine adherence",
    )
