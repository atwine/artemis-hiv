"""The backend's settings, read once from the environment. `python -m backend` loads .env first."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


@dataclass(frozen=True)
class Settings:
    # Where uvicorn listens. 127.0.0.1 keeps other devices out (ACCESS.md, role "network").
    host: str = "127.0.0.1"
    port: int = 8000
    # The app's own pages. Any other Origin is refused (ACCESS.md, role "website").
    allowed_origins: Tuple[str, ...] = DEFAULT_ORIGINS
    # The names this backend answers to. Any other Host is refused (DNS rebinding).
    allowed_hosts: Tuple[str, ...] = ("localhost", "127.0.0.1")
    # SQLAlchemy address of the visit-record database, e.g.
    # postgresql+psycopg://artemis:...@127.0.0.1:5434/artemis
    database_url: Optional[str] = None
    # The added patient cases, the same file (and setting) the Streamlit app uses. Read only.
    custom_patients_path: Path = PROJECT_ROOT / "Data" / "custom_patients.json"


def _list(value: Optional[str], default: Tuple[str, ...]) -> Tuple[str, ...]:
    items = tuple(v.strip() for v in (value or "").split(",") if v.strip())
    return items or default


def settings_from_env() -> Settings:
    return Settings(
        host=(os.getenv("ARTEMIS_API_HOST") or "127.0.0.1").strip(),
        port=int(os.getenv("ARTEMIS_API_PORT") or 8000),
        allowed_origins=_list(os.getenv("ARTEMIS_API_ORIGINS"), DEFAULT_ORIGINS),
        database_url=(os.getenv("ARTEMIS_DATABASE_URL") or "").strip() or None,
        custom_patients_path=Path(os.getenv("ARTEMIS_CUSTOM_PATIENTS_PATH") or PROJECT_ROOT / "Data" / "custom_patients.json"),
    )
