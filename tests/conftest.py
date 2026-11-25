"""Safety net for every test: visit records never go to the real Data folder."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _visit_records_in_a_temporary_folder(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARTEMIS_VISIT_RECORDS_DIR", str(tmp_path_factory.mktemp("visit_records")))
