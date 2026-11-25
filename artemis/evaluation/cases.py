"""Evaluation cases: a frozen patient record plus its answer key (Phase 2).

One JSON file per case in eval/cases/. The answer key lists the safety problems the case
should raise (each with a word rule and the guideline passage behind it), the things the app
must not say, or that nothing should be flagged. In Phase 2 the key is a draft written from
the guidelines; the doctor reviews it in Phase 7 (owner, 2026-11-25).

A word rule is a list of groups of alternative words. Alert text matches when every group has
at least one of its words, case-insensitive, at the start of a word: "renal" matches "renal
function" but not "adrenal". For "must not say" items, a phrase said in the negative ("do not
switch from DTG") doesn't count. "Also fine" items are reasonable alerts that are neither
required nor counted as false alarms.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

KINDS = ("drug_harm", "clash", "monitoring", "plan")
# A negation shortly before a phrase, in the same sentence, means it wasn't said.
_NEGATED = re.compile(r"(?:\bnot\b|\bno\b|\bnever\b|n't\b|\bavoid\w*|\brather than\b|\binstead of\b|\bwithout\b)[^.;!?]{0,30}$")
NO_KEY = "not written yet"


class CaseError(ValueError):
    """A case file that can't be used as it stands."""


@dataclass(frozen=True)
class MatchRule:
    groups: Tuple[Tuple[str, ...], ...]

    @staticmethod
    def from_json(value: Any) -> "MatchRule":
        if not isinstance(value, list) or not value or not all(
            isinstance(g, list) and g and all(isinstance(w, str) and w.strip() for w in g) for g in value
        ):
            raise CaseError("match: a non-empty list of non-empty word lists")
        return MatchRule(tuple(tuple(w.strip().lower() for w in g) for g in value))

    def matches(self, text: str, *, skip_negated: bool = False) -> bool:
        low = (text or "").lower()

        def said(word: str) -> bool:
            for m in re.finditer(r"(?<![a-z0-9])" + re.escape(word), low):
                if not (skip_negated and _NEGATED.search(low[max(0, m.start() - 40):m.start()])):
                    return True
            return False

        return all(any(said(w) for w in group) for group in self.groups)


@dataclass(frozen=True)
class Expected:
    id: str
    kind: str
    summary: str
    rule: MatchRule
    guideline: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class MustNot:
    """An id, a summary and a word rule: used for "must not say" and "also fine" items."""

    id: str
    summary: str
    rule: MatchRule


@dataclass(frozen=True)
class Case:
    case_id: str
    source: str
    patient: Dict[str, Any]
    key_status: str
    expect_clear: bool
    problems: List[Expected]
    must_not: List[MustNot]
    also_fine: List[MustNot] = field(default_factory=list)


def _ids_unique(items: List[Any], what: str) -> None:
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        raise CaseError(f"duplicate {what} id")


def _items(entries: Any) -> List[MustNot]:
    return [MustNot(id=str(m["id"]), summary=str(m.get("summary") or ""), rule=MatchRule.from_json(m.get("match")))
            for m in entries or []]


def _parse_key(key: Dict[str, Any]) -> Tuple[str, bool, List[Expected], List[MustNot], List[MustNot]]:
    problems = []
    for p in key.get("problems") or []:
        if p.get("kind") not in KINDS:
            raise CaseError(f"kind must be one of {KINDS}: {p.get('kind')!r}")
        problems.append(Expected(
            id=str(p["id"]), kind=p["kind"], summary=str(p.get("summary") or ""),
            rule=MatchRule.from_json(p.get("match")), guideline=p.get("guideline"),
        ))
    must_not = _items(key.get("must_not"))
    also_fine = _items(key.get("also_fine"))
    expect_clear = bool(key.get("expect_clear"))
    if expect_clear == bool(problems):
        raise CaseError("expect_clear: a case either expects nothing flagged or lists problems, not both or neither")
    _ids_unique(problems, "problem")
    _ids_unique(must_not, "must_not")
    _ids_unique(also_fine, "also_fine")
    return str(key.get("status") or "draft"), expect_clear, problems, must_not, also_fine


def load_case(path: Path) -> Case:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for name in ("case_id", "source", "patient"):
        if name not in data:
            raise CaseError(f"{Path(path).name}: missing {name}")
    if "answer_key" in data:
        try:
            status, expect_clear, problems, must_not, also_fine = _parse_key(data["answer_key"])
        except (KeyError, TypeError) as exc:
            raise CaseError(f"{Path(path).name}: answer_key: {exc}") from exc
    else:
        status, expect_clear, problems, must_not, also_fine = NO_KEY, False, [], [], []
    return Case(str(data["case_id"]), str(data["source"]), data["patient"], status, expect_clear, problems, must_not,
                also_fine)


def load_cases(folder: Path) -> List[Case]:
    return [load_case(p) for p in sorted(Path(folder).glob("*.json"))]


def case_file_name(case_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", case_id).strip("_") + ".json"
