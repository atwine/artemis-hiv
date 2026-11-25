"""Phase 2B fix 5e: a second model rereads the search's top results against the query and reorders them."""

from __future__ import annotations

from typing import List

from artemis.guidelines.vector_store import VectorSearchResult, VectorStore


class _Dense(VectorStore):
    def __init__(self, ids: List[str]) -> None:
        self.ids = ids
        self.asked_k = None

    def index_guidelines(self, chunks, embedder) -> int:  # type: ignore[override]
        return len(chunks)

    def query(self, query_text, embedder, top_k=5):  # type: ignore[override]
        self.asked_k = top_k
        return [VectorSearchResult(i, f"text of {i}", {"page_number": 1}, 0.1 * n) for n, i in enumerate(self.ids[:top_k])]


def test_the_top_results_are_reordered_by_the_rereading_score() -> None:
    from artemis.guidelines.rerank import RerankStore

    dense = _Dense(["a", "b", "c", "d"])
    scores = {"text of a": 0.1, "text of b": 0.9, "text of c": 0.5, "text of d": 0.7}
    store = RerankStore(dense, scorer=lambda query, texts: [scores[t] for t in texts], depth=30)
    found = store.query("iron with dolutegravir", embedder=None, top_k=2)
    assert [r.chunk_id for r in found] == ["b", "d"]
    assert dense.asked_k == 30                      # it rereads the search's top 30, not just the top 2
    assert found[0].distance == 0.1                 # each result keeps its meaning distance


def test_indexing_passes_straight_to_the_search() -> None:
    from artemis.guidelines.rerank import RerankStore

    dense = _Dense([])
    assert RerankStore(dense, scorer=lambda q, t: [], depth=30).index_guidelines(["x", "y"], embedder=None) == 2


def test_the_app_searches_with_the_reranking_step() -> None:
    import app
    from artemis.guidelines.rerank import RerankStore

    rag = app._get_rag_engine(prefer_chroma=False, embedding_model_name=app.EMBEDDING_MODEL, engine_version=5)
    assert isinstance(rag._vector_store, RerankStore)
