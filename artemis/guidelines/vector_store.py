"""Vector store implementations.

Local-first design:
- Primary: Chroma PersistentClient
- Fallback: in-memory cosine similarity
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from modules.embedder import Embedder
from artemis.guidelines.processor import GuidelineChunk


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    document: str
    metadata: Dict[str, Any]
    distance: float


def index_collection_name(model_name: str, guideline_paths: List[Path], version: int) -> str:
    """The stored index's name: the search model, the guideline files and a fingerprint of their
    text, so an edited, added or removed file gets a fresh index instead of old passages (G37)."""
    model_key = (model_name or "").strip().lower().replace("/", "_").replace(":", "_").replace(" ", "_")
    files_key = "_".join(p.stem.strip().lower().replace(" ", "_").replace("+", "_")[:20]
                         for p in guideline_paths)[:60] or "no_guideline"
    fingerprint = hashlib.sha256()
    for p in guideline_paths:
        fingerprint.update(p.name.encode("utf-8") + b"\0" + p.read_bytes())
    return f"uganda_hiv_guidelines__{model_key}__{files_key}__{fingerprint.hexdigest()[:10]}__v{version}"


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
            metadata={"description": "Uganda HIV guideline chunks"},
        )

    def index_guidelines(self, chunks: List[GuidelineChunk], embedder: Embedder) -> int:
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
        except Exception:
            # Rationale: fallback keeps the demo runnable even if Chroma fails to initialize.
            return InMemoryVectorStore()

    return InMemoryVectorStore()
