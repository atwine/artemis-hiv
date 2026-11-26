"""What the routes need from outside: the patients, the guideline search, the model and the database.

Tests pass stand-ins (tests/conftest.py); `default_services` builds the real ones, each only when
a route first needs it, so starting the server loads no model and builds no index.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from artemis import visit_record
from artemis.patient.store import read_json_list
from backend.settings import Settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOP_K = 5  # the Streamlit screen's default number of guideline passages per alert


@dataclass
class Services:
    patients: Callable[[], List[Dict[str, Any]]]  # the patient records as stored, in file order
    search: Callable[[], Any]  # the guideline search engine (modules.rag_engine.RagEngine)
    model_client: Callable[[], Optional[Any]]  # a fresh model client, or None when none is set up
    engine: Optional[Engine]  # the visit-record database
    app_version: str
    top_k: int = TOP_K


def _demo_patients() -> List[Dict[str, Any]]:
    """The patients the Streamlit app shows, read (never written) from the same files."""
    import os

    custom = Path(os.getenv("ARTEMIS_CUSTOM_PATIENTS_PATH") or PROJECT_ROOT / "Data" / "custom_patients.json")
    return read_json_list(PROJECT_ROOT / "Data" / "mock_patients.json") + read_json_list(custom)


@functools.lru_cache(maxsize=1)
def _search() -> Any:
    # The app's own engine, settings included, until plan item 4.3 (build the index once and
    # keep it) replaces this. Imported here so the server starts without loading the model.
    import app

    rag = app._get_rag_engine(
        prefer_chroma=True,
        embedding_model_name=getattr(app, "EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        engine_version=5,
    )
    if app.GUIDELINE_PDF_PATHS:
        rag.ensure_indexed()
    return rag


def _model_client() -> Optional[Any]:
    """The OpenAI-compatible server in .env (vLLM on the A100, or OpenRouter), or None.

    No Ollama fallback: Ollama is only for the fine-tuning experiments (docs/PLAN.md)."""
    from artemis.ai.client import OpenAICompatClient, openai_compat_config_from_env

    cfg = openai_compat_config_from_env()
    return OpenAICompatClient(cfg) if cfg is not None else None


def default_services(settings: Settings) -> Services:
    engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
    return Services(
        patients=_demo_patients,
        search=_search,
        model_client=_model_client,
        engine=engine,
        app_version=visit_record.app_version(PROJECT_ROOT),
    )
