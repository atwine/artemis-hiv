"""The app's setup: which guidelines are searched, with which search model, in which kept index.

Moved out of app.py, the Streamlit file (plan 4C.1, owner 2026-11-27), so the backend and the
evaluation start without Streamlit. Nothing here reads .env: each entry point (backend/__main__.py,
the scripts) loads it first.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import TYPE_CHECKING, List

from artemis.guidelines.sources import PRACTICE_COUNTRY, guideline_paths

if TYPE_CHECKING:
    from modules.rag_engine import RagEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Markdown conversions of the guideline PDFs keep the tables that PDF text extraction drops.
GUIDELINE_MD_DIR = PROJECT_ROOT / "Data" / "MarkDown Files"
# Only the registered guidelines of the practice country: Ugandan guidance only (owner, 2026-11-25).
GUIDELINE_PATHS: List[Path] = guideline_paths(GUIDELINE_MD_DIR, PRACTICE_COUNTRY)

# Bump when the ingestion, cleaning or chunking changes, so a fresh index is built.
# Version 2 (fix 10): the cleaner keeps '<50'-style thresholds and the text of figure blocks.
# Version 3 (G36): page numbers are the guideline's printed pages.
GUIDELINE_INDEX_VERSION = 3
# The search model that turns guideline text and questions into meanings. Phase 2B fix 5d tried
# BAAI/bge-small-en-v1.5 and fix 5f Qwen/Qwen3-Embedding-0.6B; both were dropped by their keep
# rules. The index is per model, so changing it builds a fresh one.
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@functools.lru_cache(maxsize=None)
def guideline_search(embedding_model_name: str = EMBEDDING_MODEL, *, prefer_chroma: bool = True) -> "RagEngine":
    """The guideline search, one per process: the search model, and the kept index (storage/chroma)
    named after the model and the guideline text, so an edited guideline gets a fresh index (G37).
    The first call loads the search model (slow); `ensure_indexed()` then embeds only what the
    kept index lacks. The search libraries are imported here, so importing this file stays quick."""
    from artemis.guidelines.vector_store import create_vector_store, index_collection_name
    from modules.embedder import Embedder, EmbedderConfig
    from modules.rag_engine import RagEngine

    return RagEngine(
        project_root=PROJECT_ROOT,
        guideline_paths=GUIDELINE_PATHS,
        embedder=Embedder(EmbedderConfig(model_name=embedding_model_name)),
        vector_store=create_vector_store(
            project_root=PROJECT_ROOT,
            prefer_chroma=prefer_chroma,
            collection_name=index_collection_name(embedding_model_name, GUIDELINE_PATHS, GUIDELINE_INDEX_VERSION),
        ),
    )
