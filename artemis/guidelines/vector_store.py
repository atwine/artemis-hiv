"""Vector store implementations.

Local-first design:
- Primary: Chroma PersistentClient
- Fallback: in-memory cosine similarity
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from modules.embedder import Embedder
from artemis.guidelines.processor import GuidelineChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    document: str
    metadata: Dict[str, Any]
    distance: float


def index_collection_name(model_name: str, guideline_paths: List[Path], version: int) -> str:
    """The stored index's name: the search model, the guideline files and a fingerprint of their
    text, so an edited, added or removed file gets a fresh index instead of old passages (G37)."""
    # Short enough for Chroma (3-63 letters, digits, "_" or "-"): the old name was 98 characters,
    # Chroma refused it, and the app quietly fell back to rebuilding in memory (found 2026-11-26).
    # The fingerprint covers the model, every file's name and text, and the version.
    fingerprint = hashlib.sha256(f"{model_name}\0v{version}".encode("utf-8"))
    for p in guideline_paths:
        fingerprint.update(b"\0" + p.name.encode("utf-8") + b"\0" + p.read_bytes())
    model_key = re.sub(r"[^a-z0-9]+", "-", (model_name or "model").lower()).strip("-")[:24] or "model"
    return f"guidelines_{model_key}_{fingerprint.hexdigest()[:12]}_v{version}"


class VectorStore:
    def index_guidelines(self, chunks: List[GuidelineChunk], embedder: Embedder) -> int:
        raise NotImplementedError

    def query(
        self,
        query_text: str,
        embedder: Embedder,
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        raise NotImplementedError


class ChromaVectorStore(VectorStore):
    def __init__(
        self,
        *,
        persist_path: Path,
        collection_name: str = "uganda_hiv_guidelines",
    ) -> None:
        self._persist_path = persist_path
        self._collection_name = collection_name

        # Rationale: ensure the directory exists before initializing the persistent client.
        self._persist_path.mkdir(parents=True, exist_ok=True)

        import chromadb

        # PersistentClient is the recommended way to persist locally. [src]
        # https://docs.trychroma.com/docs/run-chroma/persistent-client
        self._client = chromadb.PersistentClient(path=str(self._persist_path))

        # get_or_create_collection is documented for safe reuse. [src]
        # https://docs.trychroma.com/docs/collections/create-get-delete
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            # Rank by angle (cosine), like the in-memory store Phase 2B was measured with.
            metadata={"description": "Uganda HIV guideline chunks", "hnsw:space": "cosine"},
        )

    def _stored_ids(self, ids: List[str]) -> set:
        """Which of these passages the collection already holds, asked in batches."""
        stored: set = set()
        for i in range(0, len(ids), 500):
            stored.update(self._collection.get(ids=ids[i:i + 500], include=[])["ids"])
        return stored

    def index_guidelines(self, chunks: List[GuidelineChunk], embedder: Embedder) -> int:
        """Embed and store only the passages the collection doesn't already hold, and return how
        many that was (plan item 4.3: built once and kept). The collection's name carries a
        fingerprint of the guideline text, so an edited guideline gets a fresh, full build (G37)."""
        if not chunks:
            return 0
        stored = self._stored_ids([c.chunk_id for c in chunks])
        chunks = [c for c in chunks if c.chunk_id not in stored]
        if not chunks:
            return 0

        ids = [c.chunk_id for c in chunks]
        documents = [c.text for c in chunks]
        embeddings = embedder.encode(documents)
        metadatas = [
            {
                "page_number": c.page_number,
                "source_path": c.source_path,
            }
            for c in chunks
        ]

        # Use upsert to be idempotent across runs. [src]
        # https://docs.trychroma.com/docs/collections/update-data
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents,
        )

        return len(ids)

    def query(
        self,
        query_text: str,
        embedder: Embedder,
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        if not query_text.strip():
            return []

        query_embedding = embedder.encode([query_text])[0]

        # Query API documented here. [src]
        # https://docs.trychroma.com/docs/querying-collections/query-and-get
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        out: List[VectorSearchResult] = []
        for i in range(min(len(ids), len(documents), len(metadatas), len(distances))):
            out.append(
                VectorSearchResult(
                    chunk_id=str(ids[i]),
                    document=str(documents[i]),
                    metadata=dict(metadatas[i] or {}),
                    distance=float(distances[i]),
                )
            )
        return out


class InMemoryVectorStore(VectorStore):
    def __init__(self) -> None:
        self._ids: List[str] = []
        self._docs: List[str] = []
        self._metas: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None

    def index_guidelines(self, chunks: List[GuidelineChunk], embedder: Embedder) -> int:
        if not chunks:
            return 0

        # Add to what is already stored: the engine indexes one guideline file per call, and
        # replacing the store kept only the last file (fix 10, G30). A passage indexed again
        # replaces its old copy.
        vectors = np.asarray(embedder.encode([c.text for c in chunks]), dtype=np.float32)
        rows = list(self._embeddings) if self._embeddings is not None else []
        position = {cid: i for i, cid in enumerate(self._ids)}
        for c, vec in zip(chunks, vectors):
            meta = {"page_number": c.page_number, "source_path": c.source_path}
            if c.chunk_id in position:
                i = position[c.chunk_id]
                self._docs[i], self._metas[i], rows[i] = c.text, meta, vec
            else:
                position[c.chunk_id] = len(self._ids)
                self._ids.append(c.chunk_id)
                self._docs.append(c.text)
                self._metas.append(meta)
                rows.append(vec)
        self._embeddings = np.vstack(rows)
        return len(chunks)

    def query(
        self,
        query_text: str,
        embedder: Embedder,
        top_k: int = 5,
    ) -> List[VectorSearchResult]:
        if self._embeddings is None or not self._ids:
            return []
        if not query_text.strip():
            return []

        q = np.asarray(embedder.encode([query_text])[0], dtype=np.float32)

        # Cosine distance: 1 - cosine similarity.
        # Rationale: we use a standard similarity metric for dense embeddings.
        denom = (np.linalg.norm(self._embeddings, axis=1) * np.linalg.norm(q))
        denom = np.where(denom == 0.0, 1e-12, denom)
        sims = (self._embeddings @ q) / denom
        distances = 1.0 - sims

        k = min(top_k, distances.shape[0])
        top_idx = np.argsort(distances)[:k]

        out: List[VectorSearchResult] = []
        for i in top_idx:
            out.append(
                VectorSearchResult(
                    chunk_id=self._ids[int(i)],
                    document=self._docs[int(i)],
                    metadata=dict(self._metas[int(i)]),
                    distance=float(distances[int(i)]),
                )
            )
        return out


def create_vector_store(
    *,
    project_root: Path,
    prefer_chroma: bool = True,
    collection_name: str = "uganda_hiv_guidelines",
) -> VectorStore:
    """Factory that returns the best available vector store implementation."""

    if prefer_chroma:
        try:
            # Rationale: separate collections per embedding model to avoid mixing
            # incompatible vector spaces in persistent storage.
            return ChromaVectorStore(
                persist_path=project_root / "storage" / "chroma",
                collection_name=collection_name,
            )
        except Exception as exc:
            # Keeps the app running, but said out loud: a silent fallback hid for weeks that the
            # index was never kept (Chroma refused the name; found 2026-11-26).
            logger.warning("Chroma could not start (%s); searching an in-memory index rebuilt each start", type(exc).__name__)
            return InMemoryVectorStore()

    return InMemoryVectorStore()
