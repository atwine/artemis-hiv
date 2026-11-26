"""Streamlit demo entrypoint for ARTEMIS-HIV (formerly the HIV Clinical Nudge Engine).
 
 This app implements an initial local-first “Save vs Finalize” workflow:
 - Save runs deterministic alert rules + RAG retrieval (and optional Ollama explanation)
 - Finalize is blocked until each alert is acknowledged or overridden with a reason
 """
 
from __future__ import annotations

import html
import logging
import os
import re
import uuid
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import datetime

import pandas as pd
import streamlit as st

from artemis.rules.checks import Alert
from modules.embedder import Embedder, EmbedderConfig
from modules.explanation_generator import ExplanationResult


from artemis.ai.client import (
    OllamaClient,
    OllamaConfig,
    OpenAICompatClient,
    list_ollama_models,
    openai_compat_config_from_env,
)
from artemis.patient.store import UnreadableFile, read_json_list, write_json_list
from artemis.patient.record import load_mock_patients
from modules.rag_engine import RagEngine
from artemis.guidelines.sources import PRACTICE_COUNTRY, guideline_paths
from artemis.guidelines.vector_store import VectorSearchResult, create_vector_store, index_collection_name
from artemis.patient.labs import TEST_UNITS, lab_rows_to_entries, read_lab_notes
from artemis.patient.medicines import REGIMEN_CHOICES, other_medicines, regimen_codes
from ui.labs import LAB_COLUMNS, editor_rows, lab_rows_for_display
from artemis.plan.plan_json import parse_plan
from artemis.plan.view import plan_html, read_plan
from artemis.ai.screening import NO_SEVERITY
from artemis import visit_record
from artemis.review import can_finalize as review_can_finalize, reason_options
from ui.review import finalize_visit, offer_last_saved_results, when
from ui.patient_picker import patient_label
from artemis.screen_text import DISCLAIMER, FINALIZE_BLOCKED, alert_heading, alert_references, status_banners
from ui.state import analysis_belongs_to, clear_analysis, init_analysis_state, note_changed
from artemis.visit import (
    AnalysisOptions,
    run_visit_analysis,
)


PROJECT_ROOT = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)

# Rationale: model-server settings (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY) live in a
# gitignored .env, so the app finds the vLLM server without launch flags.
# Real environment variables win over .env values (override=False).
from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env", override=False)

# Rationale: Markdown conversions of the guideline PDFs preserve table structures
# that pypdf extraction drops. We now embed from the Markdown files instead of PDFs.
GUIDELINE_MD_DIR = PROJECT_ROOT / "Data" / "MarkDown Files"
# Only the registered guidelines of the practice country: Ugandan guidance only (owner, 2026-11-25).
GUIDELINE_PATHS: list[Path] = guideline_paths(GUIDELINE_MD_DIR, PRACTICE_COUNTRY)

# Rationale: persistent Chroma collections keep old indexed chunks; bump this
# when the ingestion/cleaning/chunking logic changes to force a fresh collection.
# Version 2 (fix 10): the cleaner keeps '<50'-style thresholds and the text of figure blocks.
# Version 3 (G36): page numbers are the guideline's printed pages.
GUIDELINE_INDEX_VERSION = 3
# The search model that turns guideline text and queries into meanings (one setting the app and
# the scripts share). Phase 2B fix 5d tried BAAI/bge-small-en-v1.5 (512 word-pieces) and dropped it
# by its keep rule; fix 5f tried Qwen/Qwen3-Embedding-0.6B and dropped it the same way (it found
# more passages but the AI caught fewer problems). The index is per model, so changing it builds
# a fresh one.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MOCK_PATIENTS_PATH = PROJECT_ROOT / "Data" / "mock_patients.json"
CUSTOM_PATIENTS_PATH = Path(
    os.getenv("ARTEMIS_CUSTOM_PATIENTS_PATH") or PROJECT_ROOT / "Data" / "custom_patients.json"
)
CANDIDATE_RULES_PATH = PROJECT_ROOT / "Data" / "candidate_rules.json"


@st.cache_data
def _read_demo_patients(path: str, modified: float) -> List[Dict[str, Any]]:
    # Cached per file version: `modified` (the file's time) changes when the file is edited.
    return load_mock_patients(Path(path))


def _load_demo_patients(path: Path) -> List[Dict[str, Any]]:
    """The demo patients, reread whenever the file changes (the old cache key never changed)."""
    return _read_demo_patients(str(path), path.stat().st_mtime)


def _llm_name() -> str:
    """Display name of the model server in use, for status labels."""

    cfg = openai_compat_config_from_env()
    if cfg is None or ":11434" in cfg.base_url:
        return "Ollama"
    return "OpenRouter" if "openrouter.ai" in cfg.base_url else "vLLM"


def _save_cases(cases_file_ok: bool, items: List[Dict[str, Any]], what: str) -> bool:
    """Write the saved cases file. On failure say so on screen and return False (fix 10, G16)."""
    if not cases_file_ok:
        st.error(f"{what}: the saved cases file can't be read (see above).")
        return False
    try:
        write_json_list(CUSTOM_PATIENTS_PATH, items)
        return True
    except OSError as exc:
        logger.warning("Saved cases file not written: %s", type(exc).__name__)
        st.error(f"{what}: the saved cases file could not be written. Please try again.")
        return False


@st.cache_resource
def _get_embedder(model_name: str, *, version: int = 2) -> Embedder:
    # Rationale: embedding model load is expensive; cache the instance.
    return Embedder(EmbedderConfig(model_name=model_name))


@st.cache_resource
def _get_rag_engine(
    *,
    prefer_chroma: bool,
    embedding_model_name: str,
    engine_version: int = 3,
) -> RagEngine:
    # Rationale: keep a single vector store + embedder + engine per session.
    embedder = _get_embedder(embedding_model_name, version=2)
    # One stored index per search model and guideline text: an edited file gets a fresh one (G37).
    vector_store = create_vector_store(
        project_root=PROJECT_ROOT,
        prefer_chroma=prefer_chroma,
        collection_name=index_collection_name(embedding_model_name, GUIDELINE_PATHS, GUIDELINE_INDEX_VERSION),
    )
    return RagEngine(
        project_root=PROJECT_ROOT,
        guideline_paths=GUIDELINE_PATHS,
        embedder=embedder,
        vector_store=vector_store,
    )


def _init_session_state() -> None:
    # Rationale: Streamlit reruns on every interaction; initialize defaults once.
    init_analysis_state(st.session_state)
    # Rationale: allow adding ad-hoc test cases without editing JSON files.
    st.session_state.setdefault("custom_patients", [])


# Moved to artemis/visit.py (Phase 1). Kept under the old names for callers.


def _run_analysis(
    *,
    patient: Dict[str, Any],
    today_note: str,
    prefer_chroma: bool,
    embedding_model_name: str,
    top_k: int,
    use_ollama: bool,
    ollama_model: Optional[str],
    ollama_num_ctx: Optional[int],
) -> None:
    """Run the visit analysis (artemis/visit.py) and copy its result into session state."""
    rag = _get_rag_engine(
        prefer_chroma=prefer_chroma,
        embedding_model_name=embedding_model_name,
        # Rationale: cache-bust to refresh vector_store Chroma filter fix and related changes.
        engine_version=5,
    )
    if GUIDELINE_PATHS:
        rag.ensure_indexed()

    llm_client = None
    if use_ollama:
        remote_llm = openai_compat_config_from_env()
        if remote_llm is not None:
            llm_client = OpenAICompatClient(remote_llm)
        else:
            cfg = OllamaConfig(model=(ollama_model or "aadide/medgemma-1.5-4b-it-Q4_K_S"), num_ctx=ollama_num_ctx)
            llm_client = OllamaClient(cfg)

    env_flag = (os.getenv("AGENTIC_RAG_DEBUG") or "").strip() == "1"
    ui_flag = bool(st.session_state.get("agentic_ui_debug_enabled"))
    agentic_enabled = bool(env_flag or ui_flag)

    # Status box for any LLM activity in this run.
    ollama_status = st.status(f"{_llm_name()}: idle", expanded=False) if use_ollama else None

    def _on_status(label: str, state: str) -> None:
        if ollama_status is not None:
            ollama_status.update(label=label, state=state)

    result = run_visit_analysis(
        patient=patient,
        today_note=today_note,
        rag=rag,
        llm_client=llm_client,
        options=AnalysisOptions(top_k=top_k, use_llm=use_ollama, agentic=agentic_enabled),
        llm_name=_llm_name(),
        on_status=_on_status,
    )

    # Forget everything from the previous run, including its reviews, before storing this one.
    clear_analysis(st.session_state)
    st.session_state["analysis_patient_id"] = str(patient.get("patient_id") or "")
    st.session_state["analysis_note"] = today_note
    st.session_state["agentic_debug_enabled"] = agentic_enabled
    st.session_state["agentic_debug_result"] = result.agentic_result
    st.session_state["analysis_screening_debug"] = result.screening_debug
    st.session_state["analysis_patient_summary"] = result.patient_summary

    for alert in result.alerts:
        st.session_state[f"alert_action_{alert.alert_id}"] = "Unreviewed"
        st.session_state[f"alert_override_reason_{alert.alert_id}"] = ""
        st.session_state[f"alert_override_comment_{alert.alert_id}"] = ""

    st.session_state["analysis_ran"] = True
    st.session_state["finalized"] = False
    st.session_state["analysis_alerts"] = result.alerts
    st.session_state["analysis_results"] = result.results
    st.session_state["analysis_status"] = result.status
    st.session_state["analysis_screening_outcome"] = result.screening_outcome
    st.session_state["analysis_ollama_error"] = result.llm_error
    st.session_state["agentic_debug_reasoner"] = result.agentic_reasoner

    # Save this run to the patient's visit record (fix 9). The results stay on screen even if
    # saving fails; the screen says so.
    visit_id, saved_at = uuid.uuid4().hex, visit_record.now_utc()
    st.session_state["analysis_visit_id"] = visit_id
    st.session_state["analysis_saved_at"] = saved_at
    try:
        visit_record.append_entry(
            visit_record.records_dir(PROJECT_ROOT),
            visit_record.checks_entry(
                result,
                note=today_note,
                visit_date=str((patient.get("today_encounter") or {}).get("date") or ""),
                model=llm_client.model if llm_client is not None else None,
                app_version=visit_record.app_version(PROJECT_ROOT),
                visit_id=visit_id,
                saved_at=saved_at,
            ),
        )
    except OSError as exc:
        logger.warning("Visit record not saved: %s", type(exc).__name__)
        st.session_state["analysis_record_error"] = True


def main() -> None:
    st.set_page_config(page_title="ARTEMIS-HIV", layout="wide")
    _init_session_state()

    # Rationale: avoid modifying widget-backed session_state keys after widgets are
    # instantiated. We clear the Add patient case form on the next rerun.
    if st.session_state.pop("reset_add_case_form", False):
        for _k in [k for k in list(st.session_state.keys()) if str(k).startswith("new_case_")]:
            st.session_state.pop(_k, None)

    _flash = st.session_state.pop("add_case_flash_success", None)
    if isinstance(_flash, str) and _flash.strip():
        st.success(_flash)

    st.title("ARTEMIS-HIV")
    st.caption(DISCLAIMER)

    if not MOCK_PATIENTS_PATH.exists():
        st.error("Mock patients file not found: `Data/mock_patients.json`")
        return

    # Cache-bust: ensure edits to Data/mock_patients.json appear without manual cache clear.
    patients = _load_demo_patients(MOCK_PATIENTS_PATH)
    if not patients:
        st.error("No mock patients found in `Data/mock_patients.json`")
        return

    custom_session = list(st.session_state.get("custom_patients") or [])
    try:
        custom_disk = read_json_list(CUSTOM_PATIENTS_PATH)
        cases_file_ok = True
    except UnreadableFile as exc:
        logger.warning("Saved cases file unreadable: %s", exc)
        custom_disk, cases_file_ok = [], False
        st.error(
            "The saved cases file (custom_patients.json) can't be read, so cases can't be added or "
            "deleted until it is fixed. Nothing in it has been changed."
        )
    merged_custom: List[Dict[str, Any]] = []
    seen_ids = set()
    for p in custom_disk + custom_session:
        pid = p.get("patient_id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            merged_custom.append(p)
    custom_patients = merged_custom
    st.session_state["custom_patients"] = custom_patients

    with st.expander("Add patient case", expanded=False):
        st.markdown("""
            <div style='background-color: #FFF4E6; padding: 12px; border-radius: 6px; border-left: 4px solid #F4A261; margin-bottom: 15px;'>
                <p style='color: #E76F51; margin: 0; font-weight: 500;'>⚠️ For testing: avoid entering real names/identifiers. Use coded IDs or de-identified data.</p>
            </div>
        """, unsafe_allow_html=True)

        new_patient_id = st.text_input("Patient Identifier", key="new_case_patient_id")

        col1, col2 = st.columns(2)
        with col1:
            new_age = st.number_input(
                "Age (years)",
                min_value=0,
                max_value=120,
                value=None,
                key="new_case_age",
                help="Patient age in years"
            )
        with col2:
            new_sex = st.selectbox(
                "Sex",
                options=["", "M", "F"],
                key="new_case_sex",
                help="Biological sex"
            )

        new_art_regimen = st.multiselect(
            "Current ART regimen",
            REGIMEN_CHOICES,
            key="new_case_art_regimen",
            help="Pick a combination (TLD = TDF + 3TC + DTG) or the single drugs.",
        )

        new_other_meds = st.text_area(
            "Other Medications",
            key="new_case_other_meds",
            height=60,
            help="Non-ARV medications, one per line (e.g., ibuprofen 400 mg as needed)."
        )

        new_complaints = st.text_area(
            "Complaints & Symptoms",
            key="new_case_complaints",
            height=80,
            help="Current symptoms and patient complaints"
        )

        new_exam_findings = st.text_area(
            "Examination Findings",
            key="new_case_exam_findings",
            height=80,
            help="Physical examination findings and observations"
        )

        st.caption("Optional: enter prior labs, events, and historical notes.")
        new_prior_history = st.text_area(
            "Significant history prior to today's visit",
            key="new_case_prior_history",
            height=80
        )

        st.caption(
            "Optional: one row per lab result. Leave the unit blank for the usual unit; "
            "creatinine needs its unit when it was measured in mg/dL."
        )
        _all_units = sorted({u for units in TEST_UNITS.values() for u in units})

        def _lab_table(key: str, default_date):
            # An empty table needs explicit column types, or the date column reads as numbers.
            empty = pd.DataFrame(
                {
                    "test": pd.Series(dtype="object"),
                    "date": pd.Series(dtype="datetime64[ns]"),
                    "value": pd.Series(dtype="object"),
                    "unit": pd.Series(dtype="object"),
                }
            )[LAB_COLUMNS]
            return st.data_editor(
                empty,
                key=key,
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                column_config={
                    "test": st.column_config.SelectboxColumn("Test", options=list(TEST_UNITS)),
                    "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", default=default_date),
                    "value": st.column_config.TextColumn("Value", help="As written on the report, e.g. <50"),
                    "unit": st.column_config.SelectboxColumn("Unit", options=_all_units),
                },
            )

        st.markdown("**Today's laboratory results**")
        new_todays_lab_rows = _lab_table("new_case_today_labs", datetime.date.today())
        st.markdown("**Previous laboratory results**")
        new_previous_lab_rows = _lab_table("new_case_previous_labs", None)

        if st.button("Add case to patient list"):
            pid = (new_patient_id or "").strip()
            if not pid:
                st.error("Patient ID is required.")
            elif any((p.get("patient_id") == pid) for p in (list(patients) + custom_patients)):
                st.error("That Patient ID already exists in the current patient list.")
            else:
                encounter_iso = datetime.date.today().isoformat()


                def _records(table) -> list:
                    if hasattr(table, "to_dict"):
                        return table.to_dict("records")
                    cols = list(table or {})
                    return [dict(zip(cols, vals)) for vals in zip(*(table[c] for c in cols))] if cols else []

                labs_parsed: Dict[str, List[Dict[str, Any]]] = {}
                lab_errors: List[str] = []
                for _label, _table, _source in (
                    ("Today's", new_todays_lab_rows, "today"),
                    ("Previous", new_previous_lab_rows, "previous"),
                ):
                    _entries, _errors = lab_rows_to_entries(editor_rows(_records(_table)), source=_source)
                    lab_errors += [f"{_label} lab results, {e}" for e in _errors]
                    for _test, _rows in _entries.items():
                        labs_parsed.setdefault(_test, []).extend(_rows)
                if lab_errors:
                    for _e in lab_errors:
                        st.error(_e)
                    st.stop()

                # The picked drugs and combinations, as drug codes (TLD becomes TDF, 3TC, DTG).
                art_regimen = regimen_codes(new_art_regimen or [])
                # One medicine per line; commas inside a line are part of it.
                other_meds = other_medicines((new_other_meds or "").splitlines())

                patient_record: Dict[str, Any] = {
                    "patient_id": pid,
                    "age_years": new_age if new_age is not None else None,
                    "sex": new_sex if new_sex else None,
                    "art_regimen_current": art_regimen,
                    "other_medications": other_meds,
                    "visits": [],
                    "labs": labs_parsed,
                    "today_encounter": {
                        "date": encounter_iso,
                        "note": "",
                        "orders": [],
                        "med_changes": [],
                    },
                    "intake": {
                        "complaints_symptoms": (new_complaints or ""),
                        "examination_findings": (new_exam_findings or ""),
                        "prior_history": (new_prior_history or ""),
                    },
                }

                # BACKWARD COMPATIBILITY: Concatenate structured fields into legacy visits[] format
                # so existing code (build_patient_context, RAG, LLM prompts) continues to work
                legacy_note_parts = []
                if patient_record["intake"]["complaints_symptoms"]:
                    legacy_note_parts.append(
                        f"Complaints & Symptoms:\n{patient_record['intake']['complaints_symptoms']}"
                    )
                if patient_record["intake"]["examination_findings"]:
                    legacy_note_parts.append(
                        f"Examination Findings:\n{patient_record['intake']['examination_findings']}"
                    )
                if patient_record["intake"]["prior_history"]:
                    legacy_note_parts.append(
                        f"Significant history prior to today's visit:\n{patient_record['intake']['prior_history']}"
                    )

                if legacy_note_parts:
                    patient_record["visits"].append(
                        {
                            "date": encounter_iso,
                            "type": "intake",
                            "clinician_note": "\n\n".join(legacy_note_parts),
                        }
                    )

                # Rationale: keep the local list in sync so the newly added patient
                # appears in the list immediately on this rerun.
                if _save_cases(cases_file_ok, custom_disk + [patient_record], "The case was not added"):
                    custom_patients = custom_patients + [patient_record]
                    st.session_state["custom_patients"] = custom_patients
                    # Rationale: auto-select the newly added patient to make it clear
                    # the add succeeded.
                    st.session_state["selected_patient_label"] = patient_label(patient_record)
                    # Rationale: clear the Add patient case form after success to allow rapid entry.
                    st.session_state["add_case_flash_success"] = "Case added."
                    st.session_state["reset_add_case_form"] = True
                    st.rerun()

    if custom_patients:
        # Rationale: keep demo patients first, then any manually-added cases.
        patients = list(patients) + custom_patients

    st.subheader("Encounter")

    patient_labels = [patient_label(p) for p in patients]
    # Rationale: persist patient selection across reruns, and safely reset if the
    # selected value no longer exists (e.g., list changed).
    if (
        st.session_state.get("selected_patient_label") is None
        or st.session_state.get("selected_patient_label") not in patient_labels
    ):
        st.session_state["selected_patient_label"] = patient_labels[0]

    selected_label = st.selectbox(
        "Select patient",
        patient_labels,
        key="selected_patient_label",
    )
    selected_index = patient_labels.index(selected_label)
    patient = patients[selected_index]

    selected_patient_id = str(patient.get("patient_id") or "")
    if not analysis_belongs_to(st.session_state, selected_patient_id):
        clear_analysis(st.session_state)
    custom_patient_ids = {str(p.get("patient_id") or "") for p in (custom_patients or [])}
    can_delete_selected = bool(selected_patient_id) and selected_patient_id in custom_patient_ids

    # Display Patient Details/History in expandable section
    with st.expander("Patient Details/History", expanded=False):

        # Create 2-column layout for compact display
        col1, col2 = st.columns(2)
        
        with col1:
            # Section 1: Patient Identifier & Visit Context
            st.markdown("""
                <div style='background-color: #E8F4F8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB; margin-bottom: 15px;'>
                    <h4 style='color: #2E86AB; margin-top: 0;'>1. Patient Identifier & Visit Context</h4>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"**ID Number:** {patient.get('patient_id', 'Not recorded')}")
            age = patient.get('age_years')
            st.markdown(f"**Age:** {age if age is not None else 'Not recorded'}")
            sex = patient.get('sex')
            st.markdown(f"**Sex:** {sex if sex else 'Not recorded'}")
            visit_date = patient.get('today_encounter', {}).get('date', 'Not recorded')
            st.markdown(f"**Visit Date:** {visit_date}")
            st.markdown(f"**Visit Type:** {(patient.get('today_encounter') or {}).get('type') or 'Not recorded'}")
            st.markdown("")

            # Section 2: Current ART Regimen
            st.markdown("""
                <div style='background-color: #E8F4F8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB; margin-bottom: 15px;'>
                    <h4 style='color: #2E86AB; margin-top: 0;'>2. Current ART Regimen</h4>
                </div>
            """, unsafe_allow_html=True)
            art_regimen = patient.get('art_regimen_current', [])
            if art_regimen:
                # Escaped: the regimen can be typed text, and this line is drawn as HTML.
                regimen_str = html.escape(", ".join(str(x) for x in art_regimen))
                st.markdown(f"**Regimen:** <span style='color: #2E86AB; font-weight: 600;'>{regimen_str}</span>", unsafe_allow_html=True)
            else:
                st.markdown("**Regimen:** None recorded")
            st.markdown("")

            # Section 3: Other Medications
            st.markdown("""
                <div style='background-color: #F0F8F0; padding: 15px; border-radius: 8px; border-left: 4px solid #52B788; margin-bottom: 15px;'>
                    <h4 style='color: #52B788; margin-top: 0;'>3. Other Medications</h4>
                </div>
            """, unsafe_allow_html=True)
            other_meds = patient.get('other_medications', [])
            if other_meds:
                for med in other_meds:
                    st.markdown(f"- {med}")
            else:
                st.markdown("None recorded")

        with col2:
            # Section 4: Complaints & Symptoms
            st.markdown("""
                <div style='background-color: #FFF4E6; padding: 15px; border-radius: 8px; border-left: 4px solid #F4A261; margin-bottom: 15px;'>
                    <h4 style='color: #E76F51; margin-top: 0;'>4. Complaints & Symptoms</h4>
                </div>
            """, unsafe_allow_html=True)
            intake = patient.get('intake', {})
            complaints = intake.get('complaints_symptoms', '')
            if complaints:
                st.markdown(complaints)
            else:
                st.markdown("None recorded")
            st.markdown("")

            # Section 5: Examination Findings
            st.markdown("""
                <div style='background-color: #F0F8F0; padding: 15px; border-radius: 8px; border-left: 4px solid #52B788; margin-bottom: 15px;'>
                    <h4 style='color: #52B788; margin-top: 0;'>5. Examination Findings</h4>
                </div>
            """, unsafe_allow_html=True)
            exam_findings = intake.get('examination_findings', '')
            if exam_findings:
                st.markdown(exam_findings)
            else:
                st.markdown("None recorded")
            st.markdown("")

            # Section 6: Significant history prior to today's visit
            st.markdown("""
                <div style='background-color: #F5F0FF; padding: 15px; border-radius: 8px; border-left: 4px solid #7B68AB; margin-bottom: 15px;'>
                    <h4 style='color: #7B68AB; margin-top: 0;'>6. Significant history prior to today's visit</h4>
                </div>
            """, unsafe_allow_html=True)
            prior_history = intake.get('prior_history', '')
            if prior_history:
                st.markdown(prior_history)
            else:
                st.markdown("None recorded")

            # Section 7: Today's laboratory results
            st.markdown("""
                <div style='background-color: #FFF9E6; padding: 15px; border-radius: 8px; border-left: 4px solid #FFC107; margin-bottom: 15px;'>
                    <h4 style='color: #856404; margin-top: 0;'>7. Today's laboratory results</h4>
                </div>
            """, unsafe_allow_html=True)
            _visit = datetime.date.fromisoformat(patient["today_encounter"]["date"])
            _notes = read_lab_notes(patient)

            def _show_labs(today: bool) -> None:
                rows = lab_rows_for_display(patient, _visit, today=today)
                pasted = [n.text for n in _notes if (n.source == "today") == today]
                if rows:
                    st.table(rows)
                for text in pasted:
                    st.markdown(text)
                if not rows and not pasted:
                    st.markdown("None recorded")

            _show_labs(today=True)
            st.markdown("")
            
            # Section 8: Previous Laboratory results
            st.markdown("""
                <div style='background-color: #E6F3FF; padding: 15px; border-radius: 8px; border-left: 4px solid #4A90E2; margin-bottom: 15px;'>
                    <h4 style='color: #2E5C8A; margin-top: 0;'>8. Previous Laboratory results</h4>
                </div>
            """, unsafe_allow_html=True)
            
            _show_labs(today=False)

        # Rationale: clinicians may need to remove a custom test case and re-enter it.
        with st.expander("Delete Record", expanded=False):
            if not can_delete_selected:
                st.caption(
                    "Delete is available only for custom cases you added (stored in Data/custom_patients.json)."
                )
            if st.button(
                "Delete patient",
                key="delete_selected_patient",
                disabled=not can_delete_selected,
            ):
                st.session_state["pending_delete_patient_id"] = selected_patient_id

            if (
                st.session_state.get("pending_delete_patient_id") == selected_patient_id
                and can_delete_selected
            ):
                st.warning(
                    "This will permanently delete the selected patient case and cannot be reversed."
                )
                _confirm_key = f"confirm_delete_patient_{selected_patient_id}"
                _confirmed = st.checkbox(
                    "I understand this cannot be reversed",
                    key=_confirm_key,
                )
                if st.button(
                    "Confirm delete",
                    key=f"confirm_delete_{selected_patient_id}",
                    disabled=not _confirmed,
                ):
                    if _save_cases(
                        cases_file_ok,
                        [p for p in custom_disk if str(p.get("patient_id") or "") != selected_patient_id],
                        "Nothing was deleted",
                    ):
                        custom_patients = [
                            p
                            for p in (custom_patients or [])
                            if str(p.get("patient_id") or "") != selected_patient_id
                        ]
                        st.session_state["custom_patients"] = custom_patients

                        # Rationale: reset derived UI state that may reference the deleted patient.
                        # IMPORTANT: do not set selected_patient_label here; the selectbox widget
                        # with key selected_patient_label has already been instantiated this run.
                        # On rerun, the pre-selectbox guard will reset the selection if it no
                        # longer exists in the patient list.
                        clear_analysis(st.session_state)
                        st.session_state.pop("pending_delete_patient_id", None)
                        st.success(f"Deleted patient case: {selected_patient_id}")
                        st.rerun()

    today_note_default = (patient.get("today_encounter", {}) or {}).get("note") or ""
    # Rationale: key by patient_id so switching patients shows the correct note input.
    today_note = st.text_area(
        "Clinician's Assessment & Plan",
        value=today_note_default,
        height=140,
        key=f"today_note_{patient.get('patient_id')}",
    )

    with st.expander("Advanced settings", expanded=False):
        prefer_chroma = st.checkbox("Prefer Chroma (persistent)", value=True)
        embedding_model_name = st.text_input(
            "Embedding model (SentenceTransformers)",
            value=EMBEDDING_MODEL,
        )
        top_k = st.slider("Top-K guideline chunks", min_value=1, max_value=10, value=5)
        
        
        # Agentic plan (experimental): enable ARTEMIS Review + debug expanders
        _agentic_ui_default = bool(st.session_state.get("agentic_ui_debug_enabled", False))
        agentic_ui_debug_enabled = st.checkbox(
            "Enable agentic ARTEMIS Review (experimental)",
            value=_agentic_ui_default,
            help=(
                "When enabled, runs the agentic planner using the LLM to generate a consolidated "
                "patient-level management plan (JSON) and related debug info. Requires 'Use the LLM' above."
            ),
        )
        st.session_state["agentic_ui_debug_enabled"] = bool(agentic_ui_debug_enabled)

    with st.expander("LLM settings", expanded=False):
        use_ollama = st.checkbox("Use the LLM for screening and explanations (if available)", value=True)
        remote_llm_cfg = openai_compat_config_from_env()
        if remote_llm_cfg is not None:
            # Rationale: an OpenAI-compatible server (vLLM now, OpenRouter later) is set,
            # so the Ollama-only controls (local model list, num_ctx) do not apply.
            st.caption(
                f"{_llm_name()} server (address in .env)  \n"
                f"Model: {remote_llm_cfg.model or 'first one the server lists'}  \n"
                "Set in .env (LLM_BASE_URL, LLM_MODEL)."
            )
            ollama_model_ui: Optional[str] = None
            num_ctx = 8192
        else:
            st.warning(
                "No model server is set (LLM_BASE_URL in .env), so the app falls back to a "
                "local Ollama server."
            )
            env_model = (os.getenv("OLLAMA_MODEL") or "").strip()

            discovered_models, ollama_error = list_ollama_models()
            if ollama_error:
                st.warning(
                    f"Ollama isn't reachable ({ollama_error}; OLLAMA_HOST in .env), so the list below is "
                    "only the default model and the AI review will fail until Ollama is running."
                )
            base_options: List[str] = []
            if discovered_models:
                base_options = list(dict.fromkeys(discovered_models))  # preserve order, de-dup
            else:
                base_options = ["aadide/medgemma-1.5-4b-it-Q4_K_S"]

            # Ensure the default demo model is always present as a fallback.
            if "aadide/medgemma-1.5-4b-it-Q4_K_S" not in base_options:
                base_options.append("aadide/medgemma-1.5-4b-it-Q4_K_S")

            model_options = base_options + ["Custom..."]
            default_index = 0
            if env_model and env_model in base_options:
                default_index = base_options.index(env_model)

            model_choice = st.selectbox("Ollama model", model_options, index=default_index)
            if model_choice == "Custom...":
                ollama_model_ui = st.text_input("Custom model tag", value=(env_model or ""))
            else:
                ollama_model_ui = model_choice
            if env_model:
                st.caption(f"OLLAMA_MODEL is set: {env_model} (UI model selection will be ignored)")
            num_ctx = st.number_input(
                "Context window (num_ctx)",
                min_value=1024,
                max_value=131072,
                value=8192,
                step=1024,
            )
        st.session_state["llm_num_ctx"] = int(num_ctx)

    save_disabled = not bool(GUIDELINE_PATHS)
    if st.button("Save encounter (run checks)", disabled=save_disabled):
        _run_analysis(
            patient=patient,
            today_note=today_note,
            prefer_chroma=prefer_chroma,
            embedding_model_name=embedding_model_name,
            top_k=top_k,
            use_ollama=use_ollama,
            ollama_model=ollama_model_ui,
            ollama_num_ctx=int(num_ctx),
        )

    st.subheader("Results")
    if not st.session_state.get("analysis_ran", False):
        st.info("Click 'Save encounter (run checks)' to run the analysis.")
        offer_last_saved_results(visit_record.records_dir(PROJECT_ROOT), selected_patient_id)
        return
    if st.session_state.get("analysis_restored"):
        st.caption(
            f"Saved results from {when(st.session_state.get('analysis_saved_at'))}. No new AI call was made. "
            "Press 'Save encounter (run checks)' to run the checks again."
        )
    if st.session_state.get("analysis_record_error"):
        st.warning("These results could not be saved to the visit record.")
    if note_changed(st.session_state, today_note):
        st.warning(
            "The clinician's note has changed since these results were produced. "
            "Press 'Save encounter (run checks)' to update them."
        )

    alerts: List[Alert] = st.session_state.get("analysis_alerts", [])
    status = st.session_state.get("analysis_status")

    _outcome = st.session_state.get("analysis_screening_outcome") or "not_run"
    for _kind, _text in status_banners(status, _outcome, len(alerts)):
        getattr(st, _kind)(_text)

    if status == "GREEN" and _outcome == "ok":
        st.markdown(
            "No alerts were generated: the rule checks found nothing, and the AI review of the patient "
            "summary and guideline excerpts did not find any guideline-based safety issue."
        )
        _dbg = st.session_state.get("analysis_screening_debug") or {}
        _summary = st.session_state.get("analysis_patient_summary") or {}
        _parse_status = _dbg.get("parse_status") or "unknown"
        _bundle = _dbg.get("screening_bundle") or []
        st.caption(f"AI review: reply status {_parse_status}; guideline passages shown to the AI: {len(_bundle)}.")
        with st.expander("No-alert audit trail (LLM screening)", expanded=True):
            if not _dbg and not _summary:
                st.info(
                    "Audit data was not captured for this run. Click Save again to re-run the analysis "
                    "and populate the no-alert audit trail."
                )
            st.markdown("**What the AI was given about the patient (the summary it read, with the dated notes and labs):**")
            st.json(_summary)
            st.markdown("**What guidelines the AI was shown:**")
            st.json(_bundle)
            st.markdown("**How the conclusion was reached:**")
            st.markdown(
                "- The model was instructed to extract rules ONLY from the retrieved guideline excerpts.\n"
                "- It compared them with the patient summary above, the dated notes and the lab table.\n"
                f"- LLM output status: `{_dbg.get('parse_status') or 'unknown'}`."
            )
    # Rationale: show raw LLM output for all cases (GREEN, AMBER, RED) to debug parsing issues
    _dbg = st.session_state.get("analysis_screening_debug") or {}
    if _dbg.get("raw_output"):
        with st.expander("Debug: Raw LLM screening output", expanded=False):
            st.caption(f"Parse status: {_dbg.get('parse_status') or 'unknown'}")
            st.caption(f"Why the reply ended: {_dbg.get('finish_reason') or 'not reported'}")
            if _dbg.get("client_note"):
                st.caption(str(_dbg["client_note"]))
            st.text(_dbg.get("raw_output"))

    # Rationale: use the live checkbox key ("agentic_ui_debug_enabled") so the plan
    # expanders render as soon as the checkbox is ticked, not only after a new run.
    agentic_enabled = bool(
        st.session_state.get("agentic_ui_debug_enabled", False)
        or st.session_state.get("agentic_debug_enabled", False)
    )
    # Rationale: this section is troubleshooting-only and does not help clinicians.
    # Show it only when explicitly enabled via the debug flag.
    _agentic_debug_visible = (os.getenv("AGENTIC_RAG_DEBUG") or "").strip() == "1"
    if agentic_enabled and _agentic_debug_visible:
        with st.expander("Agentic RAG debug (experimental)", expanded=False):
            agentic_result = st.session_state.get("agentic_debug_result")
            agentic_reasoner = st.session_state.get("agentic_debug_reasoner")

            if agentic_result is None and not agentic_reasoner:
                st.caption("Agentic debug is enabled but no debug data was captured for this run.")
            else:
                st.markdown("**Planner + per-subtask retrieval (Phase 1 skeleton)**")
                if isinstance(agentic_result, dict) and agentic_result.get("error"):
                    st.error(f"Agentic flow error: {agentic_result.get('error')}")
                    st.json(agentic_result)
                elif agentic_result is not None:
                    if is_dataclass(agentic_result):
                        try:
                            st.json(asdict(agentic_result))
                        except Exception:
                            st.write(agentic_result)
                    else:
                        st.write(agentic_result)

                st.markdown("**Reasoner snapshot (post-synthesis context)**")
                if agentic_reasoner is not None:
                    st.json(agentic_reasoner)
                else:
                    st.caption("No reasoner snapshot captured.")

    # Rationale: the UPDATED MANAGEMENT PLAN is rendered under the single "Output" section
    # to avoid duplicating the same content in multiple expanders.

    # Rationale: render per-alert expanders so clinicians can see each alert's
    # finding, explanation, and references.
    if alerts:
        for item in st.session_state.get("analysis_results", []):
            alert: Alert = item["alert"]
            retrieved: List[VectorSearchResult] = item["retrieved"]
            explanation: ExplanationResult = item["explanation"]

            with st.expander(alert_heading(alert), expanded=True):
                # Rationale: present clinician-facing text without inline citation fragments
                # and keep numbered references in one place for readability.
                _finding_text = str(alert.message or "")
                _finding_text = re.sub(
                    r"\[\s*chunk_id\s*:\s*[^\],]+\s*,\s*page_number\s*:\s*(\d+)\s*\]",
                    "",
                    _finding_text,
                    flags=re.IGNORECASE,
                )
                _finding_text = re.sub(r"\(page\s*=\s*\d+\)", "", _finding_text, flags=re.IGNORECASE)
                _finding_text = re.sub(
                    r"chunk[_\s]*id\s*[:=]\s*[^\s,\)\]]+",
                    "",
                    _finding_text,
                    flags=re.IGNORECASE,
                )

                _why_text = str(explanation.text or "")
                _why_text = re.sub(
                    r"\[\s*chunk_id\s*:\s*[^\],]+\s*,\s*page_number\s*:\s*(\d+)\s*\]",
                    "",
                    _why_text,
                    flags=re.IGNORECASE,
                )
                _why_text = re.sub(r"\(page\s*=\s*\d+\)", "", _why_text, flags=re.IGNORECASE)
                _why_text = re.sub(
                    r"chunk[_\s]*id\s*[:=]\s*[^\s,\)\]]+",
                    "",
                    _why_text,
                    flags=re.IGNORECASE,
                )

                # Rationale: some explanations include duplicated headings and large raw
                # dictionaries; strip them so the main UI reads like a normal note.
                _why_text = re.sub(r"^\s*why this alert\s*:\s*", "", _why_text, flags=re.IGNORECASE)
                _why_text = re.split(r"\bpatient evidence\s*:\s*", _why_text, maxsplit=1, flags=re.IGNORECASE)[0]
                _why_text = re.split(r"\bguideline excerpts\s*:\s*", _why_text, maxsplit=1, flags=re.IGNORECASE)[0]


                if alert.source == "ai":
                    _sev = (alert.evidence or {}).get("severity") or NO_SEVERITY
                    if _sev == NO_SEVERITY:
                        st.warning(
                            "Severity not given: the AI's severity was missing or not one of "
                            "critical, high, moderate or low."
                        )
                    else:
                        st.caption(f"Severity: {_sev}")

                st.markdown("**Finding**")
                st.write(_finding_text.strip() or "-")

                # Rationale: for LLM screening alerts, show the recommended_action
                # instead of duplicating the finding text under "Why this alert?".
                _rec_action = (alert.evidence or {}).get("recommended_action") or ""
                if _rec_action.strip():
                    st.markdown("**Recommended Action**")
                    st.write(_rec_action.strip())
                else:
                    st.markdown("**Why this alert?**")
                    st.write(_why_text.strip() or "-")

                # Rationale: keep technical retrieval details available without cluttering the main view.
                with st.expander("Details (debug)", expanded=False):
                    # Rationale: keep references out of the main alert view; only show them in Details.
                    _ref_heading, _ref_lines = alert_references(alert, retrieved)
                    if _ref_lines:
                        st.markdown(f"**{_ref_heading}**")
                        st.markdown("\n".join(f"{i + 1}. {line}" for i, line in enumerate(_ref_lines)))

                    # Rationale: move generation status/latency out of the main clinician view.
                    if alert.source == "ai":
                        st.caption("Finding and recommended action written by the AI review.")
                    else:
                        st.caption("Finding written by the rule check, from the patient's record.")

                    st.markdown("**Guideline retrieval**")
                    if retrieved:
                        for r in retrieved:
                            st.markdown(
                                f"- page={r.metadata.get('page_number')} | distance={r.distance:.4f} | chunk_id={r.chunk_id}"
                            )
                    else:
                        st.write("No guideline chunks retrieved.")

                # Rationale: allow promoting useful LLM-screening issues into a
                # candidate list for future deterministic rules without changing
                # rule logic at runtime.
                if alert.source == "ai":
                    if st.button(
                        "Mark as candidate deterministic rule",
                        key=f"candidate_rule_{alert.alert_id}",
                    ):
                        try:
                            existing_rules = read_json_list(CANDIDATE_RULES_PATH)
                        except UnreadableFile as exc:
                            logger.warning("Candidate rules file unreadable: %s", exc)
                            st.error("candidate_rules.json can't be read, so nothing was saved.")
                            existing_rules = None
                        # Avoid duplicating the same alert_id in the candidate file.
                        existing_ids = {
                            str(r.get("alert_id")) for r in existing_rules or [] if isinstance(r, dict)
                        }
                        if existing_rules is not None and alert.alert_id not in existing_ids:
                            candidate: Dict[str, Any] = {
                                "alert_id": alert.alert_id,
                                "title": alert.title,
                                "message": alert.message,
                                "evidence": alert.evidence,
                            }
                            existing_rules.append(candidate)
                            try:
                                write_json_list(CANDIDATE_RULES_PATH, existing_rules)
                                st.success("Marked as candidate deterministic rule (saved under Data/candidate_rules.json).")
                            except OSError as exc:
                                logger.warning("Candidate rule not saved: %s", type(exc).__name__)
                                st.error("The candidate rule could not be saved.")

    # Trial Result - Experimental formatted output display
    # Rationale: keep a single consolidated "Output" section even when there are no alerts,
    # so the UPDATED MANAGEMENT PLAN can still be shown under Output.
    if st.session_state.get("analysis_ran"):
        with st.expander("Output", expanded=False):
            st.caption("Experimental display format for alert output")

            if agentic_enabled:
                agentic_result = st.session_state.get("agentic_debug_result")
                updated_plan_text = None
                try:
                    if is_dataclass(agentic_result):
                        updated_plan_text = getattr(agentic_result, "updated_management_plan_text", None)
                        if updated_plan_text is None:
                            dbg = getattr(agentic_result, "debug_info", None) or {}
                            if isinstance(dbg, dict):
                                updated_plan_text = dbg.get("updated_management_plan_text")
                except Exception:
                    updated_plan_text = None

                if isinstance(updated_plan_text, str) and updated_plan_text.strip():
                    view = read_plan(
                        updated_plan_text,
                        clinician_plan_written=bool((st.session_state.get("analysis_note") or "").strip()),
                        issues=list(getattr(agentic_result, "plan_issues", []) or []),
                    )
                    if view is None:
                        st.warning("The AI's management plan could not be read, so it is not shown.")
                    else:
                        st.markdown("### ARTEMIS Review.")
                        st.markdown(plan_html(view), unsafe_allow_html=True)
                        with st.expander("View raw plan JSON", expanded=False):
                            st.json(parse_plan(updated_plan_text))
                elif isinstance(agentic_result, dict) or getattr(agentic_result, "plan_issues", None):
                    # The plan step ran but gave nothing to show: say so instead of showing nothing
                    # (D14, review finding at 1.Z).
                    _why = (
                        ", ".join(getattr(agentic_result, "plan_issues", []) or [])
                        if not isinstance(agentic_result, dict)
                        else "the plan step stopped with an error"
                    )
                    st.warning(f"The AI's management plan could not be produced ({_why}).")


    # Rationale: show review controls for EVERY alert so Finalize can pass.
    # Previously only one alert was shown, making it impossible to resolve the rest.
    if alerts and st.session_state.get("analysis_ran"):
        st.markdown("---")
        st.markdown("### Review Alerts")
        for alert in alerts:
            st.markdown(f"**{alert.title}**")
            st.radio(
                "Action",
                ["Unreviewed", "Acknowledge", "Override"],
                key=f"alert_action_{alert.alert_id}",
                horizontal=True,
            )

            if st.session_state.get(f"alert_action_{alert.alert_id}") == "Override":
                st.selectbox(
                    "Override reason (required)",
                    reason_options(st.session_state.get(f"alert_override_reason_{alert.alert_id}") or ""),
                    key=f"alert_override_reason_{alert.alert_id}",
                )
                st.text_area(
                    "Override comment (required for 'Other (say why)')",
                    key=f"alert_override_comment_{alert.alert_id}",
                    height=80,
                )
            st.markdown("---")

    can_finalize = review_can_finalize(st.session_state, alerts)
    if st.button("Finalize / Close visit", disabled=not can_finalize):
        finalize_visit(visit_record.records_dir(PROJECT_ROOT), alerts)

    if st.session_state.get("finalized"):
        st.success(f"Visit finalized and saved ({when(st.session_state.get('analysis_finalized_at'))}).")
    elif st.session_state.get("analysis_ran") and alerts and not can_finalize:
        st.info(FINALIZE_BLOCKED)

    st.markdown("""
        <div style='background-color: #E8F4F8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB; margin: 20px 0;'>
            <h3 style='color: #2E86AB; margin-top: 0;'>Status</h3>
            <p style='margin-bottom: 0;'>Workflow active: Save runs checks; Finalize requires review.</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Guidelines section moved to bottom
    with st.expander("📚 Clinical Guidelines Reference", expanded=False):
        st.markdown("""
            <div style='background-color: #F5F0FF; padding: 15px; border-radius: 8px; border-left: 4px solid #7B68AB;'>
                <h4 style='color: #7B68AB; margin-top: 0;'>Guidelines Used</h4>
            </div>
        """, unsafe_allow_html=True)
        if GUIDELINE_PATHS:
            st.write("Using Markdown guideline files:")
            for p in GUIDELINE_PATHS:
                st.markdown(f"- `{p.name}`")
            st.success(f"{len(GUIDELINE_PATHS)} guideline file(s) found.")
        else:
            st.error(
                "Guidelines PDF not found. Place it under `Data/` as specified in `initial-prompt-template.md`."
            )


if __name__ == "__main__":
    main()
