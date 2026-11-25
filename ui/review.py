"""The visit record on screen (fix 9): Finalize, and reopening a patient's last saved results."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from artemis import visit_record
from artemis.review import decisions_from_state
from artemis.rules.checks import Alert
from ui.state import clear_analysis

logger = logging.getLogger(__name__)


def when(saved_at: Optional[str]) -> str:
    """A saved time as "2026-11-25 16:40 UTC"."""
    return (saved_at or "")[:16].replace("T", " ") + " UTC" if saved_at else "unknown time"


def _restore_visit(checks: Dict[str, Any], finalized: Optional[Dict[str, Any]]) -> None:
    """Button callback: put a saved visit back on screen, with no new AI call (fix 9b)."""
    try:
        values = visit_record.restore(checks, finalized)
    except (ValueError, TypeError, KeyError) as exc:
        logger.warning("Saved visit could not be reopened: %s", type(exc).__name__)
        st.session_state["visit_reopen_failed"] = True
        return
    clear_analysis(st.session_state)
    st.session_state.update(values)


def offer_last_saved_results(folder: Path, patient_id: str) -> None:
    """A button to reopen the patient's last saved results. Nothing appears until it is pressed."""
    if st.session_state.pop("visit_reopen_failed", False):
        st.warning(
            "The last saved results could not be reopened. "
            "Press 'Save encounter (run checks)' to run the checks again."
        )
    try:
        entries, unreadable = visit_record.read_entries(folder, patient_id)
    except OSError as exc:
        logger.warning("Visit record could not be read: %s", type(exc).__name__)
        st.warning("This patient's visit record could not be opened.")
        return
    if unreadable:
        st.warning(f"{unreadable} line(s) of this patient's visit record could not be read and were skipped.")
    last = visit_record.last_visit(entries)
    if last is None:
        return
    checks, finalized = last
    label = f"Show last saved results ({when(checks.get('saved_at'))}{', finalized' if finalized else ''})"
    st.button(label, on_click=_restore_visit, args=(checks, finalized))


def finalize_visit(folder: Path, alerts: List[Alert]) -> None:
    """Save the clinician's decisions; the visit counts as finalized only once they are saved."""
    saved_at = visit_record.now_utc()
    entry = visit_record.finalized_entry(
        visit_id=st.session_state.get("analysis_visit_id"),
        patient_id=str(st.session_state.get("analysis_patient_id") or ""),
        decisions=decisions_from_state(st.session_state, alerts),
        saved_at=saved_at,
    )
    try:
        visit_record.append_entry(folder, entry)
    except OSError as exc:
        logger.warning("Visit record not saved at Finalize: %s", type(exc).__name__)
        st.error("The decisions could not be saved, so the visit is not finalized. Please try again.")
        return
    st.session_state["finalized"] = True
    st.session_state["analysis_finalized_at"] = saved_at
