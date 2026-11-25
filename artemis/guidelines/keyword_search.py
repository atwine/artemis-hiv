"""Keyword search beside meaning search (Phase 2B fix 5c).

The meaning search turns a whole passage into one average, so a table of drug interactions or
monitoring intervals blurs: even its own exact words didn't bring it back (the Phase 2B self-check
missed 7 Ugandan tables). Keyword search (BM25, the standard scoring that rewards rare words a
passage shares with the query, like "rifampicin" or "TDF") ranks those first. The two ranked
lists are merged by reciprocal rank fusion: a passage ranked well by both searches comes first.

HybridStore wraps the app's meaning search, so every search path (the AI screening, the
citations, the plan step) uses both.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Sequence, Tuple

from artemis.guidelines.processor import GuidelineChunk
from artemis.guidelines.vector_store import VectorSearchResult, VectorStore

K1, B = 1.5, 0.75  # BM25's usual settings
FUSION_K = 60  # reciprocal rank fusion's usual constant
DEPTH = 30  # results taken from each search before merging


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class KeywordIndex:
    """BM25 over the guideline passages, kept in memory (a few hundred passages)."""

    def __init__(self) -> None:
        self._chunks: Dict[str, GuidelineChunk] = {}
        self._counts: Dict[str, Counter] = {}

    def add(self, chunks: Sequence[GuidelineChunk]) -> None:
        for c in chunks:  # a passage indexed again replaces its old copy
            self._chunks[c.chunk_id] = c
            self._counts[c.chunk_id] = Counter(_words(c.text))

    def __len__(self) -> int:
        return len(self._chunks)

    def top(self, text: str, k: int) -> List[Tuple[GuidelineChunk, float]]:
        query = set(_words(text))
        n = len(self._chunks)
        if not query or not n:
            return []
        lengths = {cid: sum(c.values()) for cid, c in self._counts.items()}
        avg = sum(lengths.values()) / n
        df = {w: sum(1 for c in self._counts.values() if w in c) for w in query}
        scores = []
        for cid, counts in self._counts.items():
            s = 0.0
            for w in query:
                tf = counts.get(w, 0)
                if tf:
                    idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                    s += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * lengths[cid] / avg))
            if s > 0:
                scores.append((s, cid))
        scores.sort(key=lambda x: (-x[0], x[1]))
        return [(self._chunks[cid], s) for s, cid in scores[:k]]


def fuse(rankings: Sequence[Sequence[str]], k: int = FUSION_K) -> List[str]:
    """Reciprocal rank fusion: each list adds 1 / (k + rank) to a passage's score."""
    score: Dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking, start=1):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + rank)
    return sorted(score, key=lambda cid: (-score[cid], cid))


class HybridStore(VectorStore):
    """The app's meaning search plus keyword search, merged."""

    def __init__(self, dense: VectorStore, depth: int = DEPTH) -> None:
        self._dense = dense
        self._keywords = KeywordIndex()
        self._depth = depth

    def index_guidelines(self, chunks: List[GuidelineChunk], embedder: Any) -> int:
        self._keywords.add(chunks)
        return self._dense.index_guidelines(chunks, embedder)

    def query(self, query_text: str, embedder: Any, top_k: int = 5) -> List[VectorSearchResult]:
        # Every passage gets its meaning distance (it is saved and shown), so the meaning search
        # scores them all; at a few hundred passages that is cheap.
        dense = self._dense.query(query_text, embedder, top_k=max(len(self._keywords), self._depth))
        by_id = {r.chunk_id: r for r in dense}
        keyword = [c.chunk_id for c, _ in self._keywords.top(query_text, self._depth)]
        order = fuse([[r.chunk_id for r in dense[: self._depth]], keyword])
        return [by_id[cid] for cid in order if cid in by_id][:top_k]
