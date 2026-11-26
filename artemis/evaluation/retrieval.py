"""The guideline search check (Phase 2B): did the search return the passage each problem rests on?

Each expected problem in a case names the guideline passage behind it, as a quote. A returned
passage counts as found when it holds the quote, ignoring case, spacing and formatting marks. A
long quote also counts when 8 of its words in a row are there, so a quote that the cutting split
across two passages is still found. Matching on the quote's words, not on passage ids, keeps the
gold set valid when the way the guidelines are cut changes. Problems the guidelines don't cover
have no quote; they are counted apart, since no search can find them.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from artemis.evaluation.cases import Case
from artemis.guidelines.processor import _strip_markdown_noise, extract_markdown_page_texts

WINDOW = 8  # words in a row that show a long quote is in a passage


@dataclass(frozen=True)
class GoldPassage:
    document: str  # the guideline file's stem
    quote: str


@dataclass(frozen=True)
class SearchItem:
    item_id: str
    gold: Tuple[GoldPassage, ...]  # empty: the guidelines don't cover it


@dataclass(frozen=True)
class ItemResult:
    item_id: str
    covered: bool
    rank: Optional[int]  # 1-based rank of the first returned passage holding a gold quote


@dataclass(frozen=True)
class Score:
    covered: int
    not_covered: int
    found_in_5: int
    found_in_10: int
    mrr: Optional[float]


def _words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def contains_quote(passage: str, quote: str, window: int = WINDOW) -> bool:
    # Quotes are copied from the raw files, table code included; the index holds cleaned text.
    q = _words(_strip_markdown_noise(quote))
    if not q:
        return False
    hay = f" {' '.join(_words(passage))} "
    size = min(window, len(q))
    return any(f" {' '.join(q[i:i + size])} " in hay for i in range(len(q) - size + 1))


def first_hit(passages: Sequence[str], gold: Sequence[GoldPassage]) -> Optional[int]:
    for rank, text in enumerate(passages, start=1):
        if any(contains_quote(text, g.quote) for g in gold):
            return rank
    return None


def score(results: Sequence[ItemResult]) -> Score:
    covered = [r for r in results if r.covered]
    ranks = [r.rank for r in covered]
    return Score(
        covered=len(covered),
        not_covered=len(results) - len(covered),
        found_in_5=sum(1 for r in ranks if r is not None and r <= 5),
        found_in_10=sum(1 for r in ranks if r is not None and r <= 10),
        mrr=sum(1 / r for r in ranks if r is not None) / len(ranks) if ranks else None,
    )


def _gold(entry: Any, allowed: Optional[Set[str]] = None) -> Tuple[GoldPassage, ...]:
    entries = entry if isinstance(entry, list) else [entry] if entry else []
    gold = (GoldPassage(str(e["document"]), str(e["quote"])) for e in entries)
    return tuple(g for g in gold if allowed is None or g.document in allowed)


def case_items(case: Case, allowed: Optional[Set[str]] = None) -> List[SearchItem]:
    """One search item per expected problem. With `allowed` (guideline file stems), only passages
    from those guidelines count: a problem whose only passage is from another country's guideline
    is not in the searched guidelines at all."""
    return [SearchItem(f"{case.case_id}:{p.id}", _gold(p.guideline, allowed)) for p in case.problems]


def load_search_questions(path: Path) -> List[Tuple[SearchItem, str]]:
    """The standalone questions (eval/phase2b/questions.json): each item and its question text."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(SearchItem(str(q["id"]), _gold(q["gold"])), str(q["question"])) for q in data["questions"]]


def _rows(kind: str, items: Sequence[SearchItem], returned: Sequence[Any]) -> List[Dict[str, Any]]:
    texts = [str(r.document) for r in returned]
    sources = [Path(str((r.metadata or {}).get("source_path") or "")).stem for r in returned]
    return [{"kind": kind, "item": i.item_id, "covered": bool(i.gold),
             "rank": first_hit(texts, i.gold) if i.gold else None, "sources": sources} for i in items]


def check_search(cases: Sequence[Case], questions: Sequence[Tuple[SearchItem, str]],
                 case_search: Callable[[Case], Sequence[Any]],
                 question_search: Callable[[str], Sequence[Any]],
                 allowed: Optional[Set[str]] = None,
                 ideal_search: Optional[Callable[[str], Sequence[Any]]] = None) -> List[Dict[str, Any]]:
    """One row per item: where its gold first came back in the passages its search returned.
    A case's items share the search the app runs for that visit; a question is searched as is.
    `allowed` (guideline file stems) is what the app searches; other passages can't count.
    With `ideal_search`, each covered problem is also searched with its own answer-key summary
    (kind "ideal"): the index measured apart from how the app words its searches."""
    rows: List[Dict[str, Any]] = []
    for case in cases:
        items = case_items(case, allowed)
        rows += _rows("case", items, case_search(case))
        if ideal_search is not None:
            summaries = {p.id: p.summary for p in case.problems}
            for item in items:
                if item.gold:
                    rows += _rows("ideal", [item], ideal_search(summaries[item.item_id.split(":", 1)[1]]))
    for item, question in questions:
        kept = SearchItem(item.item_id, tuple(g for g in item.gold if allowed is None or g.document in allowed))
        rows += _rows("question", [kept], question_search(question))
    return rows


def self_check(gold: Sequence[GoldPassage], search: Callable[[str], Sequence[Any]]) -> Tuple[int, List[GoldPassage]]:
    """Search each gold quote word for word: its passage should come back. When it doesn't, the
    instrument (the index, the cleaning or the matching) is at fault, not the query."""
    misses = [g for g in gold if first_hit([str(r.document) for r in search(g.quote)], [g]) is None]
    return len(gold) - len(misses), misses


def summarize_check(rows: Sequence[Dict[str, Any]]) -> Dict[str, Score]:
    return {kind: score([ItemResult(r["item"], r["covered"], r["rank"]) for r in rows if r["kind"] == kind])
            for kind in ("case", "question", "ideal") if kind != "ideal" or any(r["kind"] == "ideal" for r in rows)}


def missing_quotes(gold: Sequence[GoldPassage], folder: Path) -> List[GoldPassage]:
    """Gold quotes not found whole in their guideline file, as the app cleans it for the index."""
    missing = []
    for g in gold:
        path = Path(folder) / f"{g.document}.md"
        text = " ".join(extract_markdown_page_texts(path)) if path.exists() else ""
        if not contains_quote(text, g.quote, window=len(_words(_strip_markdown_noise(g.quote))) or 1):
            missing.append(g)
    return missing
