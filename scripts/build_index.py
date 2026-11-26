"""Build the guideline search index ahead of time, the same one the app and the backend use.

    python scripts/build_index.py

The index is kept in storage/chroma (plan item 4.3): later starts embed only the passages it
doesn't hold yet, normally none. An edited guideline gets a fresh index, since the index's name
carries a fingerprint of the guideline text. Prints how many passages were embedded and how long
the whole start took. The search model comes from ARTEMIS_MODEL_DIR (in .env) if set.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    started = time.perf_counter()
    from artemis import config  # the guideline search the backend uses too

    rag = config.guideline_search()
    if not rag.search_ready:
        print("The search model did not load, so nothing was built (see the log).")
        return 1
    added = rag.ensure_indexed() if config.GUIDELINE_PATHS else 0
    print(f"{config.EMBEDDING_MODEL}: {added} passage(s) embedded; ready in {time.perf_counter() - started:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
