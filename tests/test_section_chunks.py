"""Phase 2B fix 5b: guideline text is cut along the guideline's own sections, and tables by whole rows."""

from __future__ import annotations

from pathlib import Path

ROWS = "".join(f"<tr><td>Drug {i}</td><td>Check creatinine every {i} months on TDF</td></tr>" for i in range(1, 41))
MD = f"""Consolidated Guidelines for HIV in Uganda

## 6.1 THE GOAL OF ART
The goal is viral suppression. If VL &lt;50 copies/mL, continue.

<!-- PAGE BREAK -->
## 6.12 MONITORING
### 6.12.3 Frequency of VL
Viral load at 6 months, 12 months and then every 12 months.

<table><tr><td>Medicine</td><td>Monitoring</td></tr>{ROWS}</table>
## 6.13 SIDE EFFECTS
Efavirenz can cause vivid dreams.
"""


def _pieces(tmp_path: Path, limit: int = 400):
    from artemis.guidelines.processor import process_markdown_sections

    path = tmp_path / "ug.md"
    path.write_text(MD, encoding="utf-8")
    return process_markdown_sections(path, limit=limit)


def test_a_piece_never_crosses_a_heading_and_names_its_section(tmp_path: Path) -> None:
    pieces = _pieces(tmp_path)
    assert not any("viral suppression" in p.text and "Viral load at 6 months" in p.text for p in pieces)
    vl = next(p for p in pieces if "Viral load at 6 months" in p.text)
    assert vl.text.startswith("6.12 MONITORING > 6.12.3 Frequency of VL")
    efv = next(p for p in pieces if "vivid dreams" in p.text)
    assert efv.text.startswith("6.13 SIDE EFFECTS") and "6.12" not in efv.text


def test_pieces_keep_their_page_and_the_thresholds(tmp_path: Path) -> None:
    pieces = _pieces(tmp_path)
    goal = next(p for p in pieces if "viral suppression" in p.text)
    vl = next(p for p in pieces if "Viral load at 6 months" in p.text)
    assert (goal.page_number, vl.page_number) == (1, 2)
    assert "<50" in goal.text


def test_a_long_table_is_split_by_whole_rows_with_its_header_repeated(tmp_path: Path) -> None:
    pieces = [p for p in _pieces(tmp_path, limit=400) if "Check creatinine" in p.text]
    assert len(pieces) > 1 and all(len(p.text) <= 400 for p in pieces)
    assert all("Medicine | Monitoring" in p.text for p in pieces)            # each piece carries the column names
    for i in range(1, 41):                                                  # every row whole, in exactly one piece
        row = f"Drug {i} | Check creatinine every {i} months on TDF"
        assert sum(row in p.text for p in pieces) == 1, row


def test_piece_ids_are_unique_and_tell_the_file(tmp_path: Path) -> None:
    pieces = _pieces(tmp_path)
    assert len({p.chunk_id for p in pieces}) == len(pieces) and all(p.chunk_id.startswith("ug__") for p in pieces)


def test_the_search_index_is_built_from_section_pieces(tmp_path: Path) -> None:
    from artemis.guidelines.vector_store import InMemoryVectorStore
    from modules.rag_engine import RagEngine
    from tests.pipeline_harness import FakeEmbedder

    path = tmp_path / "ug.md"
    path.write_text(MD, encoding="utf-8")
    store = InMemoryVectorStore()
    RagEngine(project_root=tmp_path, guideline_paths=[path], embedder=FakeEmbedder(), vector_store=store).ensure_indexed()
    texts = [r.document for r in store.query("monitoring", FakeEmbedder(), top_k=1000)]
    assert any(t.startswith("6.12 MONITORING > 6.12.3 Frequency of VL") for t in texts)
