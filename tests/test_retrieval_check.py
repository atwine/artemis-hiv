"""Phase 2B: the search check finds a gold guideline quote in what the search returned, however the text was cut."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

QUOTE = "Contraindications for TDF: Renal disease and/or GFR <60ml/min"
LONG = ("Long-term use of TDF together with other nephrotoxic agents (e.g. aminoglycosides or "
        "non-steroidal anti-inflammatory agents) should nonetheless be avoided.")


def test_a_quote_is_found_whatever_the_case_spacing_or_markdown() -> None:
    from artemis.evaluation.retrieval import contains_quote

    assert contains_quote("Table 9. **Contraindications for TDF:**\n Renal disease  and/or GFR <60 ml/min. Use ABC.", QUOTE)
    assert not contains_quote("Contraindications for ABC: HLA-B*5701 positive.", QUOTE)


def test_a_quote_split_across_two_pieces_counts_where_eight_words_in_a_row_survive() -> None:
    from artemis.evaluation.retrieval import contains_quote

    first_half = "...other text. Long-term use of TDF together with other nephrotoxic agents (e.g."
    tail_only = "agents) should nonetheless be avoided. Next section."
    assert contains_quote(first_half, LONG)       # 10 words in a row
    assert not contains_quote(tail_only, LONG)    # 5 words: too little to say the passage is there


def test_a_quote_copied_with_the_files_table_code_matches_the_cleaned_passage() -> None:
    from artemis.evaluation.retrieval import contains_quote

    raw = 'Polyvalent cation products</td><td id="t49-r9-c2">DTG</td><td id="t49-r9-c3">Reduce DTG levels'
    assert contains_quote("Polyvalent cation products\tDTG\tReduce DTG levels\tUse DTG 2 hours before", raw)
    assert contains_quote("If VL < 50 copies/mL and CD4 > 200, continue.", "If VL &lt; 50 copies/mL and CD4 &gt; 200, continue.")


def test_words_are_matched_whole() -> None:
    from artemis.evaluation.retrieval import contains_quote

    assert not contains_quote("adrenal disease and or gfr 60ml min contraindications for tdf", "renal disease and/or GFR <60ml/min")


def test_the_rank_of_the_first_passage_holding_any_gold_quote() -> None:
    from artemis.evaluation.retrieval import GoldPassage, first_hit

    gold = (GoldPassage("HIV_Guidelines_ART.extraction", QUOTE), GoldPassage("SAHCS_Adult_ART_2024", LONG))
    assert first_hit(["unrelated", "also unrelated", f"... {LONG} ..."], gold) == 3
    assert first_hit(["unrelated"], gold) is None


def test_recall_and_mean_reciprocal_rank_leave_out_items_the_guidelines_dont_cover() -> None:
    from artemis.evaluation.retrieval import ItemResult, score

    results = [ItemResult("a", covered=True, rank=1), ItemResult("b", covered=True, rank=7),
               ItemResult("c", covered=True, rank=None), ItemResult("d", covered=False, rank=None)]
    s = score(results)
    assert (s.covered, s.not_covered) == (3, 1)
    assert (s.found_in_5, s.found_in_10) == (1, 2)
    assert s.mrr == pytest.approx((1 + 1 / 7) / 3)


def test_a_case_gives_one_search_item_per_expected_problem(tmp_path: Path) -> None:
    from artemis.evaluation.cases import load_case
    from artemis.evaluation.retrieval import case_items

    path = tmp_path / "S1.json"
    path.write_text(json.dumps({"case_id": "S1", "source": "test", "patient": {}, "answer_key": {
        "status": "draft", "expect_clear": False, "problems": [
            {"id": "one", "kind": "drug_harm", "summary": "x", "match": [["tdf"]],
             "guideline": {"document": "D1", "page": 1, "quote": QUOTE}},
            {"id": "two", "kind": "clash", "summary": "x", "match": [["nsaid"]],
             "guideline": [{"document": "D1", "page": 1, "quote": QUOTE}, {"document": "D2", "page": 4, "quote": LONG}]},
            {"id": "three", "kind": "plan", "summary": "x", "match": [["thyroid"]], "guideline": None}]}}),
        encoding="utf-8")
    items = {i.item_id: i for i in case_items(load_case(path))}
    assert sorted(items) == ["S1:one", "S1:three", "S1:two"]
    assert len(items["S1:two"].gold) == 2 and items["S1:three"].gold == ()  # () = not in the guidelines


def test_every_gold_quote_must_be_in_its_guideline_file(tmp_path: Path) -> None:
    from artemis.evaluation.retrieval import GoldPassage, missing_quotes

    (tmp_path / "D1.md").write_text(f"Intro\n<!-- PAGE BREAK -->\nTable 9. **{QUOTE}**.", encoding="utf-8")
    good, bad = GoldPassage("D1", QUOTE), GoldPassage("D1", "This sentence is nowhere in the file at all.")
    assert missing_quotes([good, bad], tmp_path) == [bad]
