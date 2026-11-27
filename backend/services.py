"""What the routes need from outside: the database (patients and visits), the guideline search and the model.

Tests pass stand-ins (tests/conftest.py); `default_services` builds the real ones, each only when
a route first needs it, so starting the server loads no model and builds no index.
"""

from __future__ import annotations

import datetime
import functools
import logging
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from backend import clinic_db, patients_db
from backend.settings import PROJECT_ROOT, Settings

logger = logging.getLogger(__name__)

TOP_K = 5  # guideline passages per alert (the Phase 1 screen's default, kept)


def _no_case_writer(record: Dict[str, Any], date: datetime.date, time: str) -> None:
    raise RuntimeError("No case writer is set up for these services.")


@dataclass
class Services:
    patients: Callable[[], List[Dict[str, Any]]]  # the patient records, in the order they were added
    search: Callable[[], Any]  # the guideline search engine (modules.rag_engine.RagEngine)
    model_client: Callable[[], Optional[Any]]  # a fresh model client, or None when none is set up
    engine: Optional[Engine]  # the visit-record database
    app_version: str
    top_k: int = TOP_K
    # Adds a new case. Only default_services gives it the real database; any other Services refuses,
    # so a test or script can never add to the real database by accident.
    add_case: Callable[[Dict[str, Any], datetime.date, str], None] = field(default=_no_case_writer)
    clock: Callable[[], float] = time.monotonic  # seconds, for the visit-check limit
    today: Callable[[], datetime.date] = datetime.date.today  # the board's default day, a new case's visit date


def database_patients(engine: Optional[Engine]) -> Callable[[], List[Dict[str, Any]]]:
    """Every patient, read from the database (plan 4C.2); the routes refuse first when there is none."""

    def read() -> List[Dict[str, Any]]:
        with Session(engine) as session:
            return patients_db.load_all(session)

    return read


def database_case_writer(engine: Optional[Engine]) -> Callable[[Dict[str, Any], datetime.date, str], None]:
    """Adds one new case to the database, booked at `time` on `date`, in one save (plan 4C.3); an id
    in use raises patients_db.PatientExists."""

    def add(record: Dict[str, Any], date: datetime.date, time: str) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        patients_db.add(engine, record, also=lambda session: clinic_db.booking_rows(
            session, patient_id=str(record["patient_id"]), date=date, time=time, now=now))

    return add


@functools.lru_cache(maxsize=1)
def _search() -> Any:
    # The kept guideline index (artemis/config.py, plan 4C.1). Imported here so the server starts
    # without loading the search model.
    from artemis import config

    rag = config.guideline_search()
    if config.GUIDELINE_PATHS:
        rag.ensure_indexed()
    return rag


def _model_client() -> Optional[Any]:
    """The OpenAI-compatible server in .env (vLLM on the A100, or OpenRouter), or None.

    No Ollama fallback: Ollama is only for the fine-tuning experiments (docs/PLAN.md)."""
    from artemis.ai.client import OpenAICompatClient, openai_compat_config_from_env

    cfg = openai_compat_config_from_env()
    return OpenAICompatClient(cfg) if cfg is not None else None


@functools.lru_cache(maxsize=4)
def app_version(project_root: Path) -> str:
    """The code version saved with each visit check: the git commit, or "unknown"."""
    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            cwd=project_root, capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def default_services(settings: Settings) -> Services:
    engine = create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
    if engine is None:
        logger.warning("ARTEMIS_DATABASE_URL is not set: patients and visit checks will be refused (see backend/README.md)")
    return Services(
        patients=database_patients(engine),
        search=_search,
        model_client=_model_client,
        engine=engine,
        app_version=app_version(PROJECT_ROOT),
        add_case=database_case_writer(engine),
    )
