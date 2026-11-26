"""Safety net for every test: visit records never go to the real Data folder.

Also the `api` fixture: the backend with stand-in model, search and database."""

from __future__ import annotations

from typing import Any, Iterator, Optional

import pytest


@pytest.fixture(autouse=True)
def _visit_records_in_a_temporary_folder(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTEMIS_VISIT_RECORDS_DIR", str(tmp_path_factory.mktemp("visit_records")))


class Api:
    """The backend as the Next.js frontend will call it, built around stand-ins (tests/api_fakes.py):
    a replayed model, a fixed set of guideline passages and an in-memory database."""

    def __init__(self) -> None:
        from fastapi.testclient import TestClient

        from backend.main import create_app
        from backend.services import Services
        from backend.settings import Settings
        from tests.api_fakes import FakeModel, fake_search, memory_engine, read_patients, replies_for

        self.model: Optional[Any] = FakeModel(replies_for("P001"))
        self.engine = memory_engine()
        search = fake_search()
        self.services = Services(
            patients=read_patients,
            search=lambda: search,
            model_client=lambda: self.model,
            engine=self.engine,
            app_version="test",
        )
        self.app = create_app(settings=Settings(), services=self.services)
        self.client = TestClient(self.app, base_url="http://localhost")


@pytest.fixture
def api() -> Iterator[Api]:
    a = Api()
    with a.client:
        yield a
