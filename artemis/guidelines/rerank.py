"""A re-ranking step after the meaning search (Phase 2B fix 5e).

The meaning search compares one number-list for the query with one for each passage. A re-ranker
(a cross-encoder) reads the query and a passage together and scores how well the passage answers
it; it is slower, so it rereads only the search's top 30 and reorders them. RerankStore wraps the
app's search, so every search path (the AI screening, the citations, the plan step) uses it.
"""

from __future__ import annotations

from typing import Any, Callable, List, Sequence

from artemis.guidelines.vector_store import VectorSearchResult, VectorStore

DEPTH = 30
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"

Scorer = Callable[[str, Sequence[str]], Sequence[float]]


def cross_encoder_scorer(model_name: str = RERANK_MODEL) -> Scorer:
    """Scores (query, passage) pairs with a cross-encoder, safe weights only."""
    from sentence_transformers import CrossEncoder

    model = CrossEncoder(model_name, model_kwargs={"use_safetensors": True})
    return lambda query, texts: [float(s) for s in model.predict([(query, t) for t in texts])] if texts else []


class RerankStore(VectorStore):
    """The app's meaning search, its top results reread and reordered."""

    def __init__(self, dense: VectorStore, scorer: Scorer, depth: int = DEPTH) -> None:
        self._dense = dense
        self._scorer = scorer
        self._depth = depth

    def index_guidelines(self, chunks: List[Any], embedder: Any) -> int:
        return self._dense.index_guidelines(chunks, embedder)

    def query(self, query_text: str, embedder: Any, top_k: int = 5) -> List[VectorSearchResult]:
        found = self._dense.query(query_text, embedder, top_k=max(top_k, self._depth))
        scores = self._scorer(query_text, [r.document for r in found])
        order = sorted(range(len(found)), key=lambda i: -scores[i])
        return [found[i] for i in order][:top_k]
