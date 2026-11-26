"""The search model loads from the folder set in ARTEMIS_MODEL_DIR (the owner keeps model weights on drive D)."""

from __future__ import annotations

import pytest


def test_the_search_model_is_loaded_from_the_configured_folder(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import modules.embedder as embedder_module

    seen = {}

    class FakeST:
        def __init__(self, name, device=None, model_kwargs=None, cache_folder=None):
            seen.update(name=name, cache_folder=cache_folder, model_kwargs=model_kwargs)

    monkeypatch.setattr(embedder_module, "SentenceTransformer", FakeST)
    monkeypatch.setenv("ARTEMIS_MODEL_DIR", str(tmp_path))
    embedder_module.Embedder(embedder_module.EmbedderConfig(model_name="some/model"))
    assert seen == {"name": "some/model", "cache_folder": str(tmp_path), "model_kwargs": {"use_safetensors": True}}


def test_without_the_setting_the_library_default_folder_is_used(monkeypatch: pytest.MonkeyPatch) -> None:
    import modules.embedder as embedder_module

    seen = {}

    class FakeST:
        def __init__(self, name, device=None, model_kwargs=None, cache_folder=None):
            seen["cache_folder"] = cache_folder

    monkeypatch.setattr(embedder_module, "SentenceTransformer", FakeST)
    monkeypatch.delenv("ARTEMIS_MODEL_DIR", raising=False)
    embedder_module.Embedder(embedder_module.EmbedderConfig(model_name="some/model"))
    assert seen["cache_folder"] is None
