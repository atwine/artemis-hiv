"""Copy the visit-record files (Data/visit_records, plan fix 9) into the database (plan item 4.5).

    python scripts/import_visit_records.py            # the folder in ARTEMIS_VISIT_RECORDS_DIR, or Data/visit_records
    python scripts/import_visit_records.py <folder>

The files are only read. Safe to run again: what is already in the database is counted, not
added twice. The database address is ARTEMIS_DATABASE_URL (in .env); create the tables first
with `python -m alembic -c backend/alembic.ini upgrade head`.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
from sqlmodel import Session, create_engine  # noqa: E402

from artemis import visit_record  # noqa: E402
from backend import records  # noqa: E402
from backend.settings import settings_from_env  # noqa: E402


def main(argv: list) -> int:
    load_dotenv(ROOT / ".env")
    url = settings_from_env().database_url
    if not url:
        print("Set ARTEMIS_DATABASE_URL (see backend/README.md).")
        return 2
    folder = Path(argv[1]) if len(argv) > 1 else visit_record.records_dir(ROOT)
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            report = records.import_folder(session, folder)
    finally:
        engine.dispose()
    print(f"{folder}: " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in report.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
