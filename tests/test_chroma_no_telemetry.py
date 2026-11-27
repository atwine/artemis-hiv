"""Chroma's anonymous usage reporting is off wherever the app opens Chroma (privacy hygiene,
2026-11-27: a live visit's log showed Chroma trying to send usage events)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_guideline_index_opens_chroma_with_usage_reporting_off(tmp_path):
    from artemis.guidelines.vector_store import ChromaVectorStore

    store = ChromaVectorStore(persist_path=tmp_path / "chroma", collection_name="test-index")
    assert store._client.get_settings().anonymized_telemetry is False


def test_every_place_that_opens_chroma_uses_the_one_setting():
    """No other file opens a Chroma client of its own, so none can forget the setting."""
    opened = [p.relative_to(ROOT).as_posix() for folder in ("artemis", "backend", "modules", "scripts")
              for p in (ROOT / folder).rglob("*.py") if "PersistentClient(" in p.read_text(encoding="utf-8")]
    assert opened == ["artemis/guidelines/vector_store.py"]
