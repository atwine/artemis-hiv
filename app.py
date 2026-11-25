"""Streamlit demo entrypoint for ARTEMIS-HIV (formerly the HIV Clinical Nudge Engine).
 
 This app implements an initial local-first “Save vs Finalize” workflow:
 - Save runs deterministic alert rules + RAG retrieval (and optional Ollama explanation)
 - Finalize is blocked until each alert is acknowledged or overridden with a reason
 """
 
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import datetime

import pandas as pd
import streamlit as st

from artemis.rules.checks import Alert
from modules.embedder import Embedder, EmbedderConfig
from modules.explanation_generator import ExplanationResult

import html

from modules.llm_client import (
    OllamaClient,
    OllamaConfig,
    OpenAICompatClient,
    openai_compat_config_from_env,
)
from artemis.patient.record import load_mock_patients
from modules.rag_engine import RagEngine
from modules.vector_store import VectorSearchResult, create_vector_store
from artemis.patient.labs import TEST_UNITS, lab_rows_to_entries, read_lab_notes
from artemis.patient.medicines import REGIMEN_CHOICES, other_medicines, regimen_codes
from ui.labs import LAB_COLUMNS, editor_rows, lab_rows_for_display
from ui.patient_picker import patient_label
from ui.results_banner import status_banners
from ui.state import analysis_belongs_to, clear_analysis, init_analysis_state, note_changed
from artemis.visit import (
    AnalysisOptions,
    compute_overall_status,
    extract_patient_facts_from_history,
    run_visit_analysis,
)


PROJECT_ROOT = Path(__file__).resolve().parent

# Rationale: model-server settings (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY) live in a
# gitignored .env, so the app finds the vLLM server without launch flags.
# Real environment variables win over .env values (override=False).
from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env", override=False)

CONSOLIDATED_GUIDELINE_PDF_PATH = PROJECT_ROOT / "Data" / "Consolidated-HIV-and-AIDS-Guidelines-20230516.pdf"
LEGACY_GUIDELINE_PDF_PATH = PROJECT_ROOT / "Data" / "Uganda Clinical Guidelines 2023.pdf"
NCD_GUIDELINE_PDF_PATH = (
    PROJECT_ROOT
    / "Data"
    / "Uganda+Integrated+Guidelines+for+the+management+of+NCDs-+Uganda+with+cover-FIN+14October2019.V4.pdf"
)

# Rationale: Markdown conversions of the guideline PDFs preserve table structures
# that pypdf extraction drops. We now embed from the Markdown files instead of PDFs.
GUIDELINE_MD_DIR = PROJECT_ROOT / "Data" / "MarkDown Files"
GUIDELINE_PATHS: list[Path] = sorted(
    p for p in GUIDELINE_MD_DIR.glob("*.md") if p.is_file()
) if GUIDELINE_MD_DIR.is_dir() else []

# Rationale: persistent Chroma collections keep old indexed chunks; bump this
# when the ingestion/cleaning/chunking logic changes to force a fresh collection.
GUIDELINE_INDEX_VERSION = 1
# Backward-compatible alias used by downstream code.
GUIDELINE_PDF_PATHS = GUIDELINE_PATHS
MOCK_PATIENTS_PATH = PROJECT_ROOT / "Data" / "mock_patients.json"
CUSTOM_PATIENTS_PATH = Path(
    os.getenv("ARTEMIS_CUSTOM_PATIENTS_PATH") or PROJECT_ROOT / "Data" / "custom_patients.json"
)
CANDIDATE_RULES_PATH = PROJECT_ROOT / "Data" / "candidate_rules.json"


@st.cache_data
def _load_patients(path: str, *, version: int = 1) -> List[Dict[str, Any]]:
    # Rationale: cache synthetic demo data across reruns for responsiveness.
    # The version parameter allows cache-busting when the JSON file changes.
    return load_mock_patients(Path(path))


def _resolve_ollama_host() -> str:
    """Resolve the Ollama host in the same way the Python client expects.

    Mirrors the logic in modules.llm_client.OllamaClient to avoid surprises when
    listing models vs running chat calls.
    """

    raw_host = (os.getenv("OLLAMA_HOST") or "").strip()
    if not raw_host:
        return "http://localhost:11434"
    host = raw_host
    if "://" not in host:
        host = f"http://{host}"
    host = host.replace("http://0.0.0.0", "http://localhost").replace(
        "https://0.0.0.0", "http://localhost"
    )
    return host


def _llm_name() -> str:
    """Display name of the model server in use, for status labels."""

    cfg = openai_compat_config_from_env()
    if cfg is None or ":11434" in cfg.base_url:
        return "Ollama"
    return "OpenRouter" if "openrouter.ai" in cfg.base_url else "vLLM"


def _list_ollama_models() -> List[str]:
    """Return names of locally available Ollama models.

    Uses the official ollama-python Client.list() endpoint, which queries the
    /api/tags API under the hood. [src]
    - https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
    """

    try:
        from ollama import Client  # type: ignore[import]
    except Exception:
        return []

    try:
        client = Client(host=_resolve_ollama_host(), timeout=5.0)
        resp = client.list()
    except Exception:
        return []

    models: List[str] = []

    # Newer ollama-python may return an object with a `.models` attribute; older
    # versions or direct HTTP clients may return a dict or list. Handle all
    # three forms.
    items: Any
    if hasattr(resp, "models"):
        items = resp.models  # type: ignore[attr-defined]
    elif isinstance(resp, dict):
        items = resp.get("models") or resp.get("data") or []
    else:
        items = resp

    if isinstance(items, list):
        for item in items:
            # Object-style model (e.g., dataclass with `.name`).
            if hasattr(item, "name") and isinstance(getattr(item, "name"), str):
                name = getattr(item, "name")
                if name:
                    models.append(name)
                continue

            if isinstance(item, dict):
                name = item.get("name") or item.get("model")
                if isinstance(name, str) and name:
                    models.append(name)
            elif isinstance(item, str) and item:
                models.append(item)

    return models


def _load_custom_patients(path: Path) -> List[Dict[str, Any]]:
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        out: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                out.append(item)
        return out
    except Exception:
        return []


def _save_custom_patients(path: Path, patients: List[Dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(patients, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_candidate_rules(path: Path) -> List[Dict[str, Any]]:
    try:
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        out: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict):
                out.append(item)
        return out
    except Exception:
        return []


def _save_candidate_rules(path: Path, rules: List[Dict[str, Any]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
 
 
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
    # Rationale: keep a separate Chroma collection per embedding model to avoid
    # mixing incompatible vector spaces across runs.
    model_key = (
        (embedding_model_name or "")
        .strip()
        .lower()
        .replace("/", "_")
        .replace(":", "_")
        .replace(" ", "_")
    )

    # Rationale: persistent Chroma collections keep old indexed chunks. Include the
    # active guideline sources in the collection name to prevent mixing chunks from
    # previous documents and to force a clean re-index when the source files change.
    guideline_key = "no_guideline"
    if GUIDELINE_PATHS:
        # Rationale: hash all file stems so the collection auto-resets when any
        # source file is added, removed or renamed.
        guideline_key = "_".join(
            p.stem.strip().lower().replace(" ", "_").replace("+", "_")[:20]
            for p in GUIDELINE_PATHS
        )[:80]  # keep the collection name within Chroma's limits
    vector_store = create_vector_store(
        project_root=PROJECT_ROOT,
        prefer_chroma=prefer_chroma,
        collection_name=f"uganda_hiv_guidelines__{model_key}__{guideline_key}__v{GUIDELINE_INDEX_VERSION}",
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
_extract_patient_facts_from_history = extract_patient_facts_from_history
_compute_overall_status = compute_overall_status


def _alert_resolution_ok(alert_id: str) -> bool:
    action = st.session_state.get(f"alert_action_{alert_id}")
    if action == "Acknowledge":
        return True

    if action == "Override":
        reason = (st.session_state.get(f"alert_override_reason_{alert_id}") or "").strip()
        return bool(reason)

    return False


def _can_finalize(alerts: List[Alert]) -> bool:
    if not st.session_state.get("analysis_ran", False):
        return False

    if not alerts:
        return True

    return all(_alert_resolution_ok(a.alert_id) for a in alerts)


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
    if GUIDELINE_PDF_PATHS:
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
    st.session_state["analysis_screening_patient_facts"] = result.patient_facts

    for alert in result.alerts:
        st.session_state[f"alert_action_{alert.alert_id}"] = "Unreviewed"
        st.session_state[f"alert_override_reason_{alert.alert_id}"] = ""
        st.session_state[f"alert_override_comment_{alert.alert_id}"] = ""
    for alert_id, seconds in result.explain_seconds.items():
        st.session_state[f"explain_time_{alert_id}"] = seconds

    st.session_state["analysis_ran"] = True
    st.session_state["finalized"] = False
    st.session_state["analysis_alerts"] = result.alerts
    st.session_state["analysis_results"] = result.results
    st.session_state["analysis_status"] = result.status
    st.session_state["analysis_screening_outcome"] = result.screening_outcome
    st.session_state["analysis_use_ollama"] = bool(use_ollama)
    st.session_state["analysis_ollama_error"] = result.llm_error
    st.session_state["agentic_debug_reasoner"] = result.agentic_reasoner


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
    st.caption(
        "Decision support only. Clinician retains final authority. Synthetic data only."
    )

    if not MOCK_PATIENTS_PATH.exists():
        st.error("Mock patients file not found: `Data/mock_patients.json`")
        return

    # Cache-bust: ensure edits to Data/mock_patients.json appear without manual cache clear.
    patients = _load_patients(str(MOCK_PATIENTS_PATH), version=2)
    if not patients:
        st.error("No mock patients found in `Data/mock_patients.json`")
        return

    custom_session = list(st.session_state.get("custom_patients") or [])
    custom_disk = _load_custom_patients(CUSTOM_PATIENTS_PATH)
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
                custom_patients = custom_patients + [patient_record]
                st.session_state["custom_patients"] = custom_patients
                _save_custom_patients(CUSTOM_PATIENTS_PATH, custom_patients)
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
            st.markdown("**Visit Type:** Routine")
            st.markdown("")

            # Section 2: Current ART Regimen
            st.markdown("""
                <div style='background-color: #E8F4F8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB; margin-bottom: 15px;'>
                    <h4 style='color: #2E86AB; margin-top: 0;'>2. Current ART Regimen</h4>
                </div>
            """, unsafe_allow_html=True)
            art_regimen = patient.get('art_regimen_current', [])
            if art_regimen:
                regimen_str = ", ".join(art_regimen)
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
                    custom_patients = [
                        p
                        for p in (custom_patients or [])
                        if str(p.get("patient_id") or "") != selected_patient_id
                    ]
                    st.session_state["custom_patients"] = custom_patients
                    _save_custom_patients(CUSTOM_PATIENTS_PATH, custom_patients)

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
            value="all-MiniLM-L6-v2",
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
                f"{_llm_name()} server: {remote_llm_cfg.base_url}  \n"
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

            discovered_models = _list_ollama_models()
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

    save_disabled = not bool(GUIDELINE_PDF_PATHS)
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
        return
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
    if _outcome == "failed" and st.session_state.get("analysis_ollama_error"):
        st.caption(f"{_llm_name()} debug: {st.session_state.get('analysis_ollama_error')}")

    if status == "GREEN" and _outcome == "ok":
        st.markdown(
            "No alerts were generated: the rule checks found nothing, and the AI review of the patient "
            "summary and guideline excerpts did not find any guideline-based safety issue."
        )
        _dbg = st.session_state.get("analysis_screening_debug") or {}
        _facts = st.session_state.get("analysis_screening_patient_facts") or {}
        _parse_status = _dbg.get("parse_status") or "unknown"
        _bundle = _dbg.get("screening_bundle") or []
        _meds = (_facts.get("medications_detected") or []) if isinstance(_facts, dict) else []
        _symptoms = (_facts.get("symptoms_detected") or []) if isinstance(_facts, dict) else []
        st.caption(
            f"LLM screening audit: parse_status={_parse_status}; guideline_excerpts={len(_bundle)}; "
            f"meds_detected={len(_meds)}; symptoms_detected={len(_symptoms)}"
        )
        with st.expander("No-alert audit trail (LLM screening)", expanded=True):
            if not _dbg and not _facts:
                st.info(
                    "Audit data was not captured for this run. Click Save again to re-run the analysis "
                    "and populate the no-alert audit trail."
                )
            st.markdown("**What patient facts were checked (from Patient History):**")
            st.json(_facts)
            st.markdown("**What guidelines were checked (retrieved excerpts):**")
            st.json(_bundle)
            st.markdown("**How the conclusion was reached:**")
            st.markdown(
                "- The model was instructed to extract rules ONLY from the retrieved guideline excerpts.\n"
                "- It compared those extracted rules to the patient facts in the history and Stage 1 summary.\n"
                f"- LLM output status: `{_dbg.get('parse_status') or 'unknown'}`."
            )
            # Rationale: show raw output for all cases to debug empty output issues
            with st.expander("Debug: Raw LLM output", expanded=False):
                st.text(_dbg.get("raw_output") or "(no output captured)")
    # Rationale: show raw LLM output for all cases (GREEN, YELLOW, RED) to debug parsing issues
    _dbg = st.session_state.get("analysis_screening_debug") or {}
    if _dbg.get("raw_output"):
        with st.expander("Debug: Raw LLM screening output", expanded=False):
            st.caption(f"Parse status: {_dbg.get('parse_status') or 'unknown'}")
            # Rationale: show dedup stats so we can verify repetition removal is working.
            if _dbg.get("dedup_stats"):
                st.caption("Dedup stats per alert:")
                for ds in _dbg["dedup_stats"]:
                    st.caption(
                        f"  {ds['alert_id']}: {ds['raw_words']}→{ds['clean_words']} words, "
                        f"{ds['raw_chars']}→{ds['clean_chars']} chars"
                    )
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

            _source = "AI review" if getattr(alert, "source", "rule") == "ai" else "Rule check"
            with st.expander(f"Alert ({_source}): {alert.title}", expanded=True):
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

                # Rationale: build a single numbered reference list from evidence + retrieved pages.
                _pages: List[int] = []
                try:
                    _cit = (alert.evidence or {}).get("citations") or []
                    if isinstance(_cit, list):
                        for c in _cit:
                            if isinstance(c, dict) and c.get("page_number") is not None:
                                try:
                                    _pages.append(int(c.get("page_number")))
                                except Exception:
                                    continue
                except Exception:
                    _pages = []
                if retrieved:
                    for r in retrieved:
                        try:
                            p = (getattr(r, "metadata", {}) or {}).get("page_number")
                            if p is not None:
                                _pages.append(int(p))
                        except Exception:
                            continue

                # Rationale: keep compatible with older Python versions (avoid built-in generics like set[int]).
                _seen_pages = set()
                _ref_pages: List[int] = []
                for p in _pages:
                    if isinstance(p, int) and p not in _seen_pages:
                        _seen_pages.add(p)
                        _ref_pages.append(p)

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
                    if _ref_pages:
                        st.markdown("**References**")
                        st.markdown(
                            "\n".join([f"{i+1}. Guidelines, p.{p}" for i, p in enumerate(_ref_pages)])
                        )

                    # Rationale: move generation status/latency out of the main clinician view.
                    if st.session_state.get("analysis_use_ollama"):
                        st.caption("Deterministic fallback explanation (LLM unavailable).")
                        err = st.session_state.get("analysis_ollama_error")
                        if err:
                            st.caption(f"{_llm_name()} debug: {err}")
                    else:
                        st.caption("Deterministic fallback explanation (LLM disabled).")

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
                if (alert.evidence or {}).get("type") == "llm_screening":
                    if st.button(
                        "Mark as candidate deterministic rule",
                        key=f"candidate_rule_{alert.alert_id}",
                    ):
                        existing_rules = _load_candidate_rules(CANDIDATE_RULES_PATH)
                        # Avoid duplicating the same alert_id in the candidate file.
                        existing_ids = {
                            str(r.get("alert_id")) for r in existing_rules if isinstance(r, dict)
                        }
                        if alert.alert_id not in existing_ids:
                            candidate: Dict[str, Any] = {
                                "alert_id": alert.alert_id,
                                "title": alert.title,
                                "message": alert.message,
                                "evidence": alert.evidence,
                            }
                            existing_rules.append(candidate)
                            _save_candidate_rules(CANDIDATE_RULES_PATH, existing_rules)
                            st.success("Marked as candidate deterministic rule (saved under Data/candidate_rules.json).")

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
                    # Rationale: per clinician preference, hide the plan section unless we can
                    # render a clean, readable plan.
                    obj = None
                    plan_html_text = None
                    try:
                        # Rationale: same robust JSON extraction as the standalone expander.
                        _raw2 = updated_plan_text.strip()
                        if _raw2.startswith("```"):
                            _lines2 = _raw2.splitlines()
                            if _lines2[0].strip().startswith("```"):
                                _lines2 = _lines2[1:]
                            if _lines2 and _lines2[-1].strip().startswith("```"):
                                _lines2 = _lines2[:-1]
                            _raw2 = "\n".join(_lines2).strip()
                        _brace2 = _raw2.find("{")
                        if _brace2 > 0:
                            _raw2 = _raw2[_brace2:]
                        # Extract the first complete top-level JSON object using brace matching
                        _start2 = _raw2.find("{")
                        if _start2 == -1:
                            raise ValueError("No JSON object start '{' found in plan text")
                        _depth2 = 0
                        _in_str2 = False
                        _esc2 = False
                        _end2 = None
                        for _j in range(_start2, len(_raw2)):
                            _ch2 = _raw2[_j]
                            if _in_str2:
                                if _esc2:
                                    _esc2 = False
                                elif _ch2 == "\\":
                                    _esc2 = True
                                elif _ch2 == '"':
                                    _in_str2 = False
                            else:
                                if _ch2 == '"':
                                    _in_str2 = True
                                elif _ch2 == '{':
                                    _depth2 += 1
                                elif _ch2 == '}':
                                    _depth2 -= 1
                                    if _depth2 == 0:
                                        _end2 = _j + 1
                                        break
                        _slice2 = _raw2[_start2:_end2] if _end2 is not None else _raw2[_start2:]
                        # Fallback: tolerate minor JSON formatting issues from LLM output
                        def _json_loads_relaxed2(text: str):
                            try:
                                return json.loads(text)
                            except Exception:
                                t2 = text
                                # 1) Remove trailing commas before closing } or ]
                                t2 = re.sub(r',\s*([}\]])', r'\1', t2)
                                # 2a) Quote single-quoted keys if present
                                t2 = re.sub(r"([\{\[,]\s*)'([^']+)'\s*:\s*", r'\1"\2": ', t2)
                                # 2b) Quote bareword keys (letters/underscore/hyphen) if unquoted
                                t2 = re.sub(r'([\{\[,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)\s*:', r'\1"\2":', t2)
                                # 2c) Quote known keys if unquoted
                                keys_pat2 = r'(art_regimen_decision|problems|monitoring_plan|patient_counselling|decision|reason|action|problem|clinician_plan_for_this_problem|explanation)'
                                t2 = re.sub(r'([\{,\[]\s*)' + keys_pat2 + r'\s*:', r'\1"\2":', t2)
                                # 3) Convert single-quoted string values to double quotes (simple heuristic)
                                t2 = re.sub(r':\s*\'([^\']*)\'', r': "\1"', t2)
                                # 4) In arrays, convert 'item' to "item"
                                t2 = re.sub(r'\[\s*\'([^\']*)\'', r'["\1"', t2)
                                t2 = re.sub(r',\s*\'([^\']*)\'', r', "\1"', t2)
                                return json.loads(t2)
                        obj = _json_loads_relaxed2(_slice2)

                        # Render a clinician-friendly view (no raw JSON).
                        def _badge(decision: str) -> str:
                            d = (decision or "").strip().lower()
                            if d == "switch":
                                return "<span style='background:#FDECEA;color:#DC3545;padding:4px 8px;border:1px solid #DC3545;border-radius:12px;font-weight:600;'>Switch</span>"
                            if d.startswith("hold"):
                                return "<span style='background:#FFF9E6;color:#856404;padding:4px 8px;border:1px solid #FFC107;border-radius:12px;font-weight:600;'>Hold temporarily</span>"
                            return "<span style='background:#F0F8F0;color:#1B5E20;padding:4px 8px;border:1px solid #52B788;border-radius:12px;font-weight:600;'>Continue</span>"

                        def _safe(v: str) -> str:
                            return html.escape(str(v or "").strip())

                        # 1) Regimen Decision
                        ard = obj.get("art_regimen_decision") or {}
                        ard_decision = str(ard.get("decision") or "").strip()
                        ard_reason = str(ard.get("reason") or "").strip()
                        plan_html = [
                            "<div style='background:#FFFFFF;padding:14px;border-left:4px solid #2E86AB;margin-bottom:12px;border-radius:8px;'>",
                            f"<div style='margin-bottom:6px;'>{_badge(ard_decision)} <strong style='margin-left:8px;'>ART regimen decision</strong></div>",
                            f"<div style='color:#333;'>Reason: {_safe(ard_reason)}</div>",
                            "</div>",
                        ]

                        # 2) Problems → Actions (Agree/Disagree/Gap/Not Addressed)
                        probs = obj.get("problems") or []
                        if isinstance(probs, list) and probs:
                            items = []
                            for p in probs[:12]:
                                if not isinstance(p, dict):
                                    continue
                                action = _safe(p.get("action"))
                                reason = _safe(p.get("reason"))
                                cp = p.get("clinician_plan_for_this_problem") or {}
                                decision = str(cp.get("decision") or "").strip()

                                if decision in {"Gap", "Not Addressed"}:
                                    prefix = "➕ ADD"
                                    status_label = "Not in your plan"
                                    line = f"<strong>Consider adding:</strong> {action}"
                                elif decision == "Disagree":
                                    prefix = "🔄 REVIEW"
                                    status_label = "Needs review"
                                    line = f"<strong>Consider instead:</strong> {action}"
                                else:
                                    prefix = "✅ AGREE"
                                    status_label = "Matches your plan"
                                    line = f"<strong>Agree:</strong> {action}"

                                items.append(
                                    "<li style='margin-bottom:8px;'>"
                                    f"<div><span style='margin-right:6px;'>{prefix}</span> {line}</div>"
                                    f"<div style='color:#444;font-size:12px;margin-top:2px;'><em>{_safe(status_label)}</em></div>"
                                    f"<div style='color:#555;font-size:12px;margin-top:2px;'>Reason: {reason}</div>"
                                    "</li>"
                                )

                            if items:
                                plan_html += [
                                    "<div style='background-color:#F0F8F0;padding:14px;border-left:4px solid #52B788;border-radius:8px;margin-bottom:12px;'>",
                                    "<h4 style='color:#1B5E20;margin:0 0 8px 0;'>Suggested Management Plan</h4>",
                                    "<ol style='margin:0;padding-left:18px;'>" + "".join(items) + "</ol>",
                                    "</div>",
                                ]

                        # 3) Monitoring Plan
                        mp = obj.get("monitoring_plan")
                        mp_items = []
                        if isinstance(mp, list):
                            mp_items = [f"<li>{_safe(x)}</li>" for x in mp if str(x).strip()]
                        elif isinstance(mp, dict):
                            for k, v in mp.items():
                                if isinstance(v, (list, tuple)):
                                    for x in v:
                                        if str(x).strip():
                                            mp_items.append(f"<li>{_safe(x)}</li>")
                                elif str(v).strip():
                                    mp_items.append(f"<li>{_safe(v)}</li>")
                        elif isinstance(mp, str) and mp.strip():
                            mp_items = [f"<li>{_safe(mp)}</li>"]

                        if mp_items:
                            plan_html += [
                                "<div style='background:#E8F4F8;padding:14px;border-left:4px solid #2E86AB;border-radius:8px;margin-bottom:12px;'>",
                                "<h4 style='color:#2E86AB;margin:0 0 8px 0;'>Monitoring</h4>",
                                "<ul style='margin:0;padding-left:18px;'>" + "".join(mp_items) + "</ul>",
                                "</div>",
                            ]

                        # 4) Patient Counselling
                        pc = obj.get("patient_counselling") or []
                        if isinstance(pc, list) and pc:
                            pc_items = [f"<li>{_safe(x)}</li>" for x in pc if str(x).strip()]
                            if pc_items:
                                plan_html += [
                                    "<div style='background:#F5F0FF;padding:14px;border-left:4px solid #7B68AB;border-radius:8px;margin-bottom:12px;'>",
                                    "<h4 style='color:#7B68AB;margin:0 0 8px 0;'>Counselling</h4>",
                                    "<ul style='margin:0;padding-left:18px;'>" + "".join(pc_items) + "</ul>",
                                    "</div>",
                                ]

                        plan_html_text = "\n".join(plan_html) if plan_html else None
                    except Exception:
                        obj = None
                        plan_html_text = None

                    if isinstance(obj, dict) and isinstance(plan_html_text, str) and plan_html_text.strip():
                        # Rationale: match clinician-facing naming used in the example output.
                        st.markdown("### ARTEMIS Review.")
                        st.markdown(plan_html_text, unsafe_allow_html=True)

                        # Optional: raw JSON for reviewers (collapsed UI)
                        with st.expander("View raw plan JSON", expanded=False):
                            st.json(obj)


    # Rationale: show review controls for EVERY alert so _can_finalize can pass.
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
                    [
                        "",
                        "Already addressed",
                        "Not applicable",
                        "Will address later",
                        "Patient declined",
                        "Other",
                    ],
                    key=f"alert_override_reason_{alert.alert_id}",
                )
                st.text_area(
                    "Override comment (optional)",
                    key=f"alert_override_comment_{alert.alert_id}",
                    height=80,
                )
            st.markdown("---")

    can_finalize = _can_finalize(alerts)
    if st.button("Finalize / Close visit", disabled=not can_finalize):
        st.session_state["finalized"] = True

    if st.session_state.get("finalized"):
        st.success("Visit finalized.")
    elif st.session_state.get("analysis_ran") and alerts and not can_finalize:
        st.info("Finalize is disabled until all alerts are acknowledged or overridden with a reason.")

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
