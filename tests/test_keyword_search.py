"""Phase 2B fix 5c: keyword search beside meaning search, so exact guideline wording is found even in tables."""

from __future__ import annotations

import math
from typing import List

from artemis.guidelines.processor import GuidelineChunk
from artemis.guidelines.vector_store import VectorSearchResult, VectorStore

TABLE = GuidelineChunk("ug__p48", "Drug Family\tARV Drug\tInteraction\tAction\nRifampicin\tDTG\tRifampicin lowers DTG levels\t"
                       "Adjust DTG dose to twice daily\nStatins\tATV/r\tRaised statin levels\tUse low dose", "ug.md", 48)
PROSE_1 = GuidelineChunk("ug__p10", "Tuberculosis treatment should start promptly. Patients on treatment need support.", "ug.md", 10)
PROSE_2 = GuidelineChunk("ug__p11", "Adherence support helps patients stay on treatment and keep their viral load suppressed.", "ug.md", 11)


class _Dense(VectorStore):
    """A meaning search that, like the real one on tables, ranks the table last."""

    def __init__(self) -> None:
        self.indexed: List[GuidelineChunk] = []

    def index_guidelines(self, chunks, embedder) -> int:  # type: ignore[override]
        self.indexed += list(chunks)
        return len(chunks)

    def query(self, query_text, embedder, top_k=5):  # type: ignore[override]
        order = sorted(self.indexed, key=lambda c: c.chunk_id == TABLE.chunk_id)
        return [VectorSearchResult(c.chunk_id, c.text, {"source_path": c.source_path, "page_number": c.page_number}, 0.1 * (i + 1))
                for i, c in enumerate(order[:top_k])]


def test_keyword_search_ranks_the_passage_with_the_rare_exact_words_first() -> None:
    from artemis.guidelines.keyword_search import KeywordIndex

    index = KeywordIndex()
    index.add([PROSE_1, PROSE_2, TABLE])
    assert [c.chunk_id for c, _ in index.top("Does rifampicin change the dolutegravir DTG dose?", 3)][0] == "ug__p48"


def test_merging_favours_a_passage_ranked_well_by_both_searches() -> None:
    from artemis.guidelines.keyword_search import fuse

    assert fuse([["a", "b", "c"], ["b", "d", "a"]])[:2] == ["b", "a"]


def test_the_combined_search_finds_a_table_the_meaning_search_ranks_last() -> None:
    from artemis.guidelines.keyword_search import HybridStore

    dense = _Dense()
    store = HybridStore(dense)
    store.index_guidelines([PROSE_1, PROSE_2, TABLE], embedder=None)
    assert len(dense.indexed) == 3                        # the meaning search is still built
    found = store.query("rifampicin lowers DTG levels: adjust the dose", embedder=None, top_k=2)
    assert found[0].chunk_id == "ug__p48"
    assert all(not math.isnan(r.distance) for r in found)  # every result keeps a real meaning distance
    assert found[0].metadata["page_number"] == 48


def test_the_app_searches_with_the_combined_search() -> None:
    import app
    from artemis.guidelines.keyword_search import HybridStore

    rag = app._get_rag_engine(prefer_chroma=False, embedding_model_name="all-MiniLM-L6-v2", engine_version=5)
    assert isinstance(rag._vector_store, HybridStore)
