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

        from sqlmodel import Session

        import datetime

        from backend import clinic_db, patients_db
        from backend.main import create_app
        from backend.services import Services, database_case_writer, database_patients
        from backend.settings import Settings
        from tests.api_fakes import FakeModel, fake_search, memory_engine, read_clinic_day, read_patients, replies_for

        self.model: Optional[Any] = FakeModel(replies_for("P001"))
        self.added_cases: list = []  # cases added through the API (to the in-memory database, never Data/)
        self.engine = memory_engine()
        with Session(self.engine) as session:  # the seed patients and the demo day, as the backup holds them
            patients_db.import_records(session, read_patients(), origin="seed")
            clinic_db.import_schedule(session, read_clinic_day(), origin="seed")
        search = fake_search()

        writer = database_case_writer(self.engine)

        def add_case(record, date, time):
            writer(record, date, time)
            self.added_cases.append(record)

        self.services = Services(
            patients=database_patients(self.engine),
            search=lambda: search,
            model_client=lambda: self.model,
            engine=self.engine,
            app_version="test",
            today=lambda: datetime.date(2026, 11, 27),  # the day after the demo day
            add_case=add_case,
        )
        self.app = create_app(settings=Settings(), services=self.services)
        self.client = TestClient(self.app, base_url="http://localhost")


@pytest.fixture
def api() -> Iterator[Api]:
    a = Api()
    with a.client:
        yield a
