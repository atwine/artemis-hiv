"""G37: an edited guideline file gets a fresh search index instead of the old passages."""

from __future__ import annotations

from artemis.guidelines.vector_store import index_collection_name


def test_editing_a_guideline_file_names_a_new_index(tmp_path) -> None:
    f = tmp_path / "HIV_Guidelines_ART.extraction.md"
    f.write_text("Check creatinine every 12 months on TDF.\n\n234\n", encoding="utf-8")
    before = index_collection_name("all-MiniLM-L6-v2", [f], 3)
    assert index_collection_name("all-MiniLM-L6-v2", [f], 3) == before  # same text, same index
    f.write_text("Check creatinine every 6 months on TDF.\n\n234\n", encoding="utf-8")
    assert index_collection_name("all-MiniLM-L6-v2", [f], 3) != before


def test_the_index_name_differs_by_search_model_and_version(tmp_path) -> None:
    f = tmp_path / "a.md"
    f.write_text("text", encoding="utf-8")
    names = {index_collection_name(m, [f], v) for m in ("all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5") for v in (2, 3)}
    assert len(names) == 4 and all(len(n) <= 120 for n in names)
