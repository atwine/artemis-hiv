"""The guideline index is built once and kept (plan item 4.3; owner, 2026-11-26: keep Chroma,
embed only what's missing). Uses a real Chroma store in a temporary folder and a stand-in
embedder that counts what it was asked to embed, so no search model is loaded.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from artemis.guidelines.processor import GuidelineChunk
from artemis.guidelines.vector_store import ChromaVectorStore


class CountingEmbedder:
    loaded = True

    def __init__(self) -> None:
        self.embedded: List[str] = []

    def encode(self, texts: List[str]) -> List[List[float]]:
        self.embedded.extend(texts)
        return [[float(len(t)), 1.0, 0.0, 0.5] for t in texts]


def _chunks(n: int = 3) -> List[GuidelineChunk]:
    return [GuidelineChunk(chunk_id=f"doc__p{i}_c1", text=f"Passage {i} about viral load monitoring.", source_path="g.md", page_number=i)
            for i in range(1, n + 1)]


def test_the_second_start_embeds_nothing(tmp_path: Path):
    first = CountingEmbedder()
    assert ChromaVectorStore(persist_path=tmp_path, collection_name="index_c").index_guidelines(_chunks(), first) == 3
    assert len(first.embedded) == 3
    again = CountingEmbedder()
    store = ChromaVectorStore(persist_path=tmp_path, collection_name="index_c")  # as after a restart
    assert store.index_guidelines(_chunks(), again) == 0
    assert again.embedded == []
    assert [r.chunk_id for r in store.query("viral load", again, top_k=3)]  # still searchable


def test_only_missing_passages_are_embedded(tmp_path: Path):
    ChromaVectorStore(persist_path=tmp_path, collection_name="index_c").index_guidelines(_chunks(2), CountingEmbedder())
    more = CountingEmbedder()
    assert ChromaVectorStore(persist_path=tmp_path, collection_name="index_c").index_guidelines(_chunks(4), more) == 2
    assert more.embedded == ["Passage 3 about viral load monitoring.", "Passage 4 about viral load monitoring."]


def test_a_new_index_name_starts_fresh(tmp_path: Path):
    """An edited guideline gets a new fingerprint, so a new collection, so a full build."""
    ChromaVectorStore(persist_path=tmp_path, collection_name="index_one").index_guidelines(_chunks(), CountingEmbedder())
    fresh = CountingEmbedder()
    assert ChromaVectorStore(persist_path=tmp_path, collection_name="index_two").index_guidelines(_chunks(), fresh) == 3


def test_nothing_is_written_while_the_search_model_is_not_loaded(tmp_path: Path):
    """The stand-in a failed model falls back to makes near-random vectors (G33): writing them
    would be kept for good now that later starts skip what's stored."""
    from modules.rag_engine import RagEngine

    guideline = tmp_path / "HIV_Guidelines_ART.extraction.md"
    guideline.write_text("<::page 1\nCheck viral load every 6 months for patients on DTG-based ART.\n", encoding="utf-8")
    store = ChromaVectorStore(persist_path=tmp_path / "chroma", collection_name="index_c")
    broken = CountingEmbedder()
    broken.loaded = False
    engine = RagEngine(project_root=tmp_path, guideline_paths=[guideline], embedder=broken, vector_store=store)
    assert engine.ensure_indexed() == 0
    assert broken.embedded == []
    assert store._collection.count() == 0


@pytest.mark.parametrize("n", [1, 600])
def test_large_indexes_are_checked_in_batches(tmp_path: Path, n: int):
    ChromaVectorStore(persist_path=tmp_path, collection_name="index_c").index_guidelines(_chunks(n), CountingEmbedder())
    again = CountingEmbedder()
    assert ChromaVectorStore(persist_path=tmp_path, collection_name="index_c").index_guidelines(_chunks(n), again) == 0


def test_the_index_name_is_one_chroma_accepts(tmp_path: Path):
    """The old name was 98 characters; Chroma allows 63 and refused it, so the app quietly used a
    store that rebuilt everything each start (found 2026-11-26)."""
    import re

    import app
    from artemis.guidelines.vector_store import index_collection_name

    for model in (app.EMBEDDING_MODEL, "Qwen/Qwen3-Embedding-0.6B", "BAAI/bge-small-en-v1.5"):
        name = index_collection_name(model, app.GUIDELINE_PATHS, app.GUIDELINE_INDEX_VERSION)
        assert 3 <= len(name) <= 63 and re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*[A-Za-z0-9]$", name), name
        ChromaVectorStore(persist_path=tmp_path, collection_name=name)  # accepted


def test_the_index_name_still_changes_when_a_guideline_or_model_changes(tmp_path: Path):
    from artemis.guidelines.vector_store import index_collection_name

    g = tmp_path / "g.md"
    g.write_text("one", encoding="utf-8")
    first = index_collection_name("m", [g], 3)
    g.write_text("two", encoding="utf-8")
    assert index_collection_name("m", [g], 3) != first
    assert index_collection_name("other", [g], 3) != index_collection_name("m", [g], 3)
    assert index_collection_name("m", [g], 4) != index_collection_name("m", [g], 3)


def test_chroma_ranks_by_angle_like_the_measured_store(tmp_path: Path):
    """Phase 2B was measured with the in-memory store (cosine distance); Chroma must rank the same way."""
    store = ChromaVectorStore(persist_path=tmp_path, collection_name="index_cos")
    assert store._collection.metadata.get("hnsw:space") == "cosine"


def test_a_store_that_cannot_start_is_reported_not_silent(tmp_path: Path, caplog):
    import logging

    from artemis.guidelines.vector_store import InMemoryVectorStore, create_vector_store

    with caplog.at_level(logging.WARNING):
        store = create_vector_store(project_root=tmp_path, prefer_chroma=True, collection_name="x")  # too short
    assert isinstance(store, InMemoryVectorStore)
    # The error's class name differs between chromadb versions (ValueError on 0.6, InvalidArgumentError
    # on the locked 1.5), so only the warning itself is checked.
    assert any("Chroma could not start" in r.getMessage() for r in caplog.records)


def test_changing_how_passages_are_split_needs_a_new_index_version():
    """The kept index skips passage ids it already holds, so a change to how the text is split
    would keep stale passages unless the index version is bumped (same quiet failure as lesson 32)."""
    import app
    from modules.rag_engine import RagConfig

    assert (RagConfig.chunk_size, RagConfig.overlap, app.GUIDELINE_INDEX_VERSION) == (1200, 200, 3), (
        "Splitting changed: bump GUIDELINE_INDEX_VERSION in app.py, then update this test."
    )
