"""The backend's real services, set up the way the server sets them up (backend/services.py).

The other API tests swap in a stand-in search, so a name the Streamlit app renamed (Phase 2B
renamed GUIDELINE_PDF_PATHS to GUIDELINE_PATHS) went unnoticed there and made every real visit
check fail. These tests go through the real `_search` setup; only the engine builder itself
(app._get_rag_engine, which loads the search model) is replaced, so nothing is loaded or built.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest


@pytest.fixture
def real_search_setup(monkeypatch):
    import app
    from backend import services
    from tests.api_fakes import fake_search

    engine = fake_search()
    asked: Dict[str, Any] = {}
    indexed: List[bool] = []

    def build(**kwargs):
        asked.update(kwargs)
        return engine

    monkeypatch.setattr(app, "_get_rag_engine", build)
    monkeypatch.setattr(engine, "ensure_indexed", lambda **_: indexed.append(True) or 0)
    services._search.cache_clear()
    yield {"app": app, "engine": engine, "asked": asked, "indexed": indexed}
    services._search.cache_clear()


def test_search_setup_builds_the_apps_own_engine(real_search_setup):
    from backend import services

    app = real_search_setup["app"]
    assert services._search() is real_search_setup["engine"]
    assert real_search_setup["asked"] == {
        "prefer_chroma": True, "embedding_model_name": app.EMBEDDING_MODEL, "engine_version": 5,
    }
    # Indexed when the app has guideline files, as app._run_analysis does.
    assert real_search_setup["indexed"] == ([True] if app.GUIDELINE_PATHS else [])
    services._search()
    assert len(real_search_setup["indexed"]) <= 1  # built once, then kept


def test_a_visit_check_through_the_real_search_setup(real_search_setup):
    """The route with the real search setup (not a stand-in for _search): a 200 and a saved visit."""
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.services import Services, _search
    from backend.settings import Settings
    from tests.api_fakes import FakeModel, memory_engine, read_patients, replies_for

    model = FakeModel(replies_for("P001"))
    services = Services(
        patients=read_patients, search=_search, model_client=lambda: model, engine=memory_engine(), app_version="test",
    )
    with TestClient(create_app(settings=Settings(), services=services), base_url="http://localhost") as client:
        r = client.post("/api/patients/P001/visits", json={"note": "Routine follow-up."}, headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200, r.text
    assert r.json()["record_saved"] is True
    assert r.json()["cards"]


def test_model_client_setup(monkeypatch):
    """The real model-client setup: none without a server in the settings, a client with one.
    Making the client sends nothing; the address is a placeholder that is never called."""
    from artemis.ai.client import OpenAICompatClient
    from backend import services

    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    assert services._model_client() is None
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLM_MODEL", "placeholder")
    assert isinstance(services._model_client(), OpenAICompatClient)
