"""G36 (owner's decision, 2026-11-26): a citation names the guideline's printed page, not the
position of the page in our extract file."""

from __future__ import annotations

from pathlib import Path

import pytest

from artemis.guidelines.processor import printed_page_numbers, process_markdown_guidelines
from artemis.guidelines.vector_store import VectorSearchResult
from artemis.rules.checks import Alert
from artemis.screen_text import alert_references

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "Data" / "MarkDown Files" / "HIV_Guidelines_ART.extraction.md"


def test_pages_without_a_printed_number_take_it_from_their_neighbours() -> None:
    assert printed_page_numbers(["Dosing table\n\n234\n", "A page whose number was lost", "More text\n\n236"]) == [234, 235, 236]


def test_numbers_that_do_not_run_in_order_are_refused() -> None:
    with pytest.raises(ValueError):
        printed_page_numbers(["text\n\n234", "text\n\n240"])


def test_a_file_with_no_printed_numbers_is_refused() -> None:
    with pytest.raises(ValueError):
        printed_page_numbers(["no number here", "nor here"])


@pytest.mark.skipif(not ART.exists(), reason="guideline file not present")
def test_the_uganda_art_extract_cites_its_printed_pages() -> None:
    chunks = process_markdown_guidelines(ART)
    pages = sorted({c.page_number for c in chunks})
    assert pages[0] == 234 and pages[-1] == 284  # the extract is printed pages 234 to 284
    # The 22nd page of the extract is printed page 255 (audit G36: it was cited as "p.22").
    assert any(c.page_number == 255 and "__p22_" in c.chunk_id for c in chunks)


def test_a_citation_names_the_guideline_and_its_printed_page() -> None:
    passage = VectorSearchResult("x__p22_c1", "text", {"page_number": 255, "source_path": str(ART)}, 0.1)
    _, lines = alert_references(Alert("R1", "t", "m", {}, "q"), [passage])
    assert lines == ["Uganda HIV Guidelines 2022 · p. 255"]


def test_a_citation_reads_the_way_the_design_shows_it() -> None:
    """Owner, 2026-11-26 ("A, design's look"): capital G, a middle dot with spaces, "p." then a
    space and the printed page; no table or section number (plan item 8.5)."""
    from artemis.screen_text import citation_line

    assert citation_line(str(ART), 270) == "Uganda HIV Guidelines 2022 · p. 270"
    assert citation_line("somewhere/else.md", 4) == "Guidelines · p. 4"


def test_every_registered_guideline_has_printed_pages_that_run_in_order() -> None:
    from artemis.guidelines.processor import _markdown_segments
    from artemis.guidelines.sources import SOURCES

    for name in SOURCES:
        path = ROOT / "Data" / "MarkDown Files" / name
        if path.exists():
            printed_page_numbers(_markdown_segments(path))  # refuses a file it would cite wrongly
