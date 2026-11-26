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
    import app  # the app's own engine and settings, so both search the same index

    rag = app._get_rag_engine(prefer_chroma=True, embedding_model_name=app.EMBEDDING_MODEL, engine_version=5)
    if not rag.search_ready:
        print("The search model did not load, so nothing was built (see the app log).")
        return 1
    added = rag.ensure_indexed() if app.GUIDELINE_PATHS else 0
    print(f"{app.EMBEDDING_MODEL}: {added} passage(s) embedded; ready in {time.perf_counter() - started:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
