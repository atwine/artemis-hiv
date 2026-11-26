"""What the routes need from outside: the patients, the guideline search, the model and the database.

Tests pass stand-ins (tests/conftest.py); `default_services` builds the real ones, each only when
a route first needs it, so starting the server loads no model and builds no index.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.engine import Engine
from sqlmodel import create_engine

from artemis import visit_record
from artemis.patient.store import read_json_list
from backend.settings import PROJECT_ROOT, Settings

logger = logging.getLogger(__name__)

TOP_K = 5  # the Streamlit screen's default number of guideline passages per alert


@dataclass
class Services:
    patients: Callable[[], List[Dict[str, Any]]]  # the patient records as stored, in file order
    search: Callable[[], Any]  # the guideline search engine (modules.rag_engine.RagEngine)
    model_client: Callable[[], Optional[Any]]  # a fresh model client, or None when none is set up
    engine: Optional[Engine]  # the visit-record database
    app_version: str
    top_k: int = TOP_K


def demo_patients(settings: Settings) -> Callable[[], List[Dict[str, Any]]]:
    """The patients the Streamlit app shows, read (never written) from the same files."""

    def read() -> List[Dict[str, Any]]:
        return read_json_list(PROJECT_ROOT / "Data" / "mock_patients.json") + read_json_list(settings.custom_patients_path)

    return read


@functools.lru_cache(maxsize=1)
def _search() -> Any:
    # Stopgap until plan item 4.3 (build the index once and keep it): the Streamlit app's own
    # engine and settings, so both search the same index. Imported here so the server starts
    # without loading the model. engine_version=5 is the value app._run_analysis passes.
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
    if engine is None:
        logger.warning("ARTEMIS_DATABASE_URL is not set: visit checks will be refused (see backend/README.md)")
    return Services(
        patients=demo_patients(settings),
        search=_search,
        model_client=_model_client,
        engine=engine,
        app_version=visit_record.app_version(PROJECT_ROOT),
    )
