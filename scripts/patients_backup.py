"""Make or load the patients' backup, backend/seed/patients.sql (owner, 2026-11-27).

    python scripts/patients_backup.py make    # write the backup from the database
    python scripts/patients_backup.py load    # fill a database from the backup (safe to run again)

The database address is ARTEMIS_DATABASE_URL (in .env). Create the tables first with
`python -m alembic -c backend/alembic.ini upgrade head`. `make` writes a temporary file and then
renames it, so an interrupted run never leaves half a backup.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from sqlmodel import Session, create_engine, func, select  # noqa: E402

from backend import patients_backup as seed  # noqa: E402
from backend.patients_db import Patient  # noqa: E402
from backend.settings import settings_from_env  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def main(argv: list) -> int:
    if len(argv) != 2 or argv[1] not in ("make", "load"):
        print(__doc__.strip().splitlines()[2])
        print(__doc__.strip().splitlines()[3])
        return 2
    load_dotenv(ROOT / ".env")
    url = settings_from_env().database_url
    if not url:
        print("Set ARTEMIS_DATABASE_URL (see backend/README.md).")
        return 2
    engine = create_engine(url)
    try:
        if argv[1] == "make":
            with Session(engine) as session:
                _write(seed.SEED_SQL, seed.dump(session))
                added = session.exec(select(func.count()).select_from(Patient).where(Patient.origin == "added")).one()
            print(f"wrote {seed.SEED_SQL.relative_to(ROOT)}, including {added} case(s) added through the app: "
                  "the repo is public, so made-up patients only")
        else:
            added = seed.load(engine, seed.SEED_SQL.read_text(encoding="utf-8"))
            print(f"{added} row(s) added")
        with Session(engine) as session:
            print(f"{session.exec(select(func.count()).select_from(Patient)).one()} patient(s) in the database")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
