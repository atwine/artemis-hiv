"""Alembic's entry point: which database, and which tables the code describes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The repo root, so `backend` imports from any folder. (Alembic's own prepend_sys_path setting
# splits on spaces in older versions, and this repo's path has one.)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from alembic import context  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import engine_from_config, pool  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import backend.records  # noqa: F401,E402  (registers the tables on SQLModel.metadata)

config = context.config
target_metadata = SQLModel.metadata


def _url() -> str:
    # A test sets the address on the config; otherwise it comes from the environment or .env.
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        load_dotenv()
        url = os.getenv("ARTEMIS_DATABASE_URL") or ""
    if not url:
        raise SystemExit("Set ARTEMIS_DATABASE_URL (see backend/README.md).")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = engine_from_config({"sqlalchemy.url": _url()}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
