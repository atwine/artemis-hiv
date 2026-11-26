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
    # The added patient cases, the same file (and setting) the Streamlit app uses; POST /api/patients adds to it.
    custom_patients_path: Path = PROJECT_ROOT / "Data" / "custom_patients.json"
    # The design's demo-day patients P007-P009 (owner, 2026-11-26), and the demo day's schedule.
    demo_day_patients_path: Path = PROJECT_ROOT / "Data" / "demo_day_patients.json"
    clinic_day_path: Path = PROJECT_ROOT / "Data" / "demo_clinic_day.json"
    # At most this many visit checks a minute; the next gets 429 (owner, 2026-11-26).
    visit_checks_per_minute: int = 6


def _at_least_one(name: str, value: Optional[str], default: int) -> int:
    """A whole number of at least 1, checked once here; anything else stops the start with a clear error."""
    if not (value or "").strip():
        return default
    try:
        number = int(value)
    except ValueError:
        raise ValueError(f"{name} must be a whole number of at least 1, not {value!r}") from None
    if number < 1:
        raise ValueError(f"{name} must be at least 1, not {number}")
    return number


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
        visit_checks_per_minute=_at_least_one("ARTEMIS_VISIT_CHECKS_PER_MINUTE", os.getenv("ARTEMIS_VISIT_CHECKS_PER_MINUTE"),
                                              Settings.visit_checks_per_minute),
    )
