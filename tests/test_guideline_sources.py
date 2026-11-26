"""A Ugandan clinic gets Ugandan guidance only: no other country's passage can reach the search (owner, 2026-11-25)."""

from __future__ import annotations

from pathlib import Path

UGANDA = {"HIV_Guidelines_ART.extraction", "HIV_Guidelines_Co_infectionScreening.extraction"}


def test_the_app_searches_only_the_ugandan_guidelines() -> None:
    import app

    assert {p.stem for p in app.GUIDELINE_PATHS} == UGANDA


def test_a_guideline_file_dropped_in_the_folder_is_never_used_unless_registered(tmp_path: Path) -> None:
    from artemis.guidelines.sources import guideline_paths

    for name in ["HIV_Guidelines_ART.extraction.md", "SAHCS_Adult_ART_2024.md", "Some_new_country.md"]:
        (tmp_path / name).write_text("text", encoding="utf-8")
    assert [p.name for p in guideline_paths(tmp_path, "UG")] == ["HIV_Guidelines_ART.extraction.md"]


def test_every_passage_in_the_index_comes_from_a_ugandan_guideline() -> None:
    import app
    from artemis.guidelines.sources import SOURCES
    from artemis.guidelines.vector_store import InMemoryVectorStore
    from modules.rag_engine import RagEngine
    from tests.pipeline_harness import FakeEmbedder

    store = InMemoryVectorStore()
    RagEngine(project_root=app.PROJECT_ROOT, guideline_paths=app.GUIDELINE_PATHS, embedder=FakeEmbedder(),
              vector_store=store).ensure_indexed()
    countries = {SOURCES[Path(r.metadata["source_path"]).name].country for r in store.query("tenofovir", FakeEmbedder(), top_k=10_000)}
    assert countries == {"UG"}


def test_the_search_check_counts_a_problem_whose_only_passage_is_foreign_as_not_in_the_ugandan_guidelines(tmp_path: Path) -> None:
    import json

    from artemis.evaluation.cases import load_case
    from artemis.evaluation.retrieval import case_items

    (tmp_path / "S1.json").write_text(json.dumps({"case_id": "S1", "source": "test", "patient": {}, "answer_key": {
        "status": "draft", "expect_clear": False, "problems": [
            {"id": "nsaid", "kind": "clash", "summary": "x", "match": [["nsaid"]],
             "guideline": {"document": "SAHCS_Adult_ART_2024", "page": 4, "quote": "Long-term use of TDF together with other nephrotoxic agents"}},
            {"id": "tdf", "kind": "drug_harm", "summary": "x", "match": [["tdf"]],
             "guideline": [{"document": "SAHCS_Adult_ART_2024", "page": 4, "quote": "a b c d e f g h"},
                           {"document": "HIV_Guidelines_ART.extraction", "page": 10, "quote": "Contraindications for TDF: Renal disease"}]}]}}),
        encoding="utf-8")
    items = {i.item_id: i for i in case_items(load_case(tmp_path / "S1.json"), allowed=UGANDA)}
    assert items["S1:nsaid"].gold == ()
    assert [g.document for g in items["S1:tdf"].gold] == ["HIV_Guidelines_ART.extraction"]
