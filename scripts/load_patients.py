"""Load the made-up patients from the seed files into the database (plan 4C.2).

    python scripts/load_patients.py

Reads Data/mock_patients.json, Data/custom_patients.json and Data/demo_day_patients.json (only
read, never written) and adds each patient the database doesn't have yet, in one save. Safe to run
again: a patient already there is skipped, so cases added through the website are never touched.
The demo answer keys (expected_demo_outcome) stay in the files, for the evaluation. The database
address is ARTEMIS_DATABASE_URL (in .env); create the tables first with
`python -m alembic -c backend/alembic.ini upgrade head`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from sqlmodel import Session, create_engine  # noqa: E402

from artemis.patient.store import read_json_list  # noqa: E402
from backend import patients_db  # noqa: E402
from backend.settings import settings_from_env  # noqa: E402

# In the order the app has always listed them.
SEED_FILES = [ROOT / "Data" / name for name in ("mock_patients.json", "custom_patients.json", "demo_day_patients.json")]


def seed_records() -> list:
    return [record for path in SEED_FILES for record in read_json_list(path)]


def main() -> int:
    load_dotenv(ROOT / ".env")
    url = settings_from_env().database_url
    if not url:
        print("Set ARTEMIS_DATABASE_URL (see backend/README.md).")
        return 2
    records = seed_records()
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            added = patients_db.import_records(session, records, origin="seed")
    finally:
        engine.dispose()
    print(f"{len(records)} seed patient(s): {added} added, {len(records) - added} already in the database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
