"""Check the search database holds Ugandan guidance only.

    python scripts/check_index_sources.py

Opens the app's saved search database (storage/chroma), lists every collection with its size and
the guideline files its pieces came from, and exits with 1 if any piece comes from a file that is
not a registered guideline of the practice country (artemis/guidelines/sources.py). Reads only.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artemis.guidelines.sources import PRACTICE_COUNTRY, SOURCES  # noqa: E402

DB = ROOT / "storage" / "chroma"


def main() -> int:
    allowed = {f for f, s in SOURCES.items() if s.country == PRACTICE_COUNTRY}
    if not DB.exists():
        print(f"no search database at {DB.relative_to(ROOT)}; the app builds it on first use")
        return 0
    import chromadb

    client = chromadb.PersistentClient(path=str(DB))
    bad = 0
    collections = client.list_collections()
    print(f"{len(collections)} collection(s) in {DB.relative_to(ROOT)}")
    for col in collections:
        col = client.get_collection(col.name) if not hasattr(col, "count") else col
        metas = col.get(include=["metadatas"])["metadatas"] or []
        files = Counter(Path(str((m or {}).get("source_path") or "?")).name for m in metas)
        foreign = {f: n for f, n in files.items() if f not in allowed}
        bad += sum(foreign.values())
        print(f"- {col.name}: {len(metas)} pieces")
        for f, n in sorted(files.items()):
            print(f"    {n:>5}  {f}{'   <-- NOT a registered ' + PRACTICE_COUNTRY + ' guideline' if f in foreign else ''}")
    print("OK: every piece comes from a registered Ugandan guideline" if not bad else f"FAIL: {bad} pieces from other files")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
