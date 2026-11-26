"""Phase 2B fix 5f: a search model that wants its questions marked gets them marked; guideline text stays plain."""

from __future__ import annotations

from typing import Any, List

import numpy as np


class _Model:
    prompts = {"query": "Instruct: find the guideline passage\nQuery: "}

    def __init__(self) -> None:
        self.calls: List[Any] = []

    def encode(self, texts, prompt_name=None):
        self.calls.append((list(texts), prompt_name))
        return np.ones((len(texts), 3))


def test_questions_get_the_models_query_instruction_and_passages_do_not() -> None:
    from modules.embedder import Embedder

    embedder = Embedder.__new__(Embedder)
    embedder._model = _Model()
    embedder.encode(["a guideline passage"])
    embedder.encode_queries(["iron with dolutegravir?"])
    assert embedder._model.calls == [(["a guideline passage"], None), (["iron with dolutegravir?"], "query")]


def test_a_model_without_a_query_instruction_encodes_questions_plain() -> None:
    from modules.embedder import Embedder

    model = _Model()
    model.prompts = {}
    embedder = Embedder.__new__(Embedder)
    embedder._model = model
    embedder.encode_queries(["iron with dolutegravir?"])
    assert model.calls == [(["iron with dolutegravir?"], None)]


class _Recording:
    def __init__(self) -> None:
        self.queries: List[str] = []

    def encode(self, texts):
        return [[1.0, 0.0] for _ in texts]

    def encode_queries(self, texts):
        self.queries += list(texts)
        return [[1.0, 0.0] for _ in texts]


def test_the_search_store_encodes_the_search_text_as_a_question() -> None:
    from artemis.guidelines.processor import GuidelineChunk
    from artemis.guidelines.vector_store import InMemoryVectorStore

    store, embedder = InMemoryVectorStore(), _Recording()
    store.index_guidelines([GuidelineChunk("c1", "passage", "ug.md", 1)], embedder)
    store.query("iron with dolutegravir?", embedder, top_k=1)
    assert embedder.queries == ["iron with dolutegravir?"]
