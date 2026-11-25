"""Scoring one run of the app against a case's answer key, and summarising many runs (Phase 2).

For each run: which expected problems some alert caught, which were missed, how many alerts
caught nothing expected (extra), and which "must not say" items an alert said. Across runs:

- sensitivity: caught / expected, over runs of cases that have problems
- precision: alerts that caught something / all alerts
- specificity: runs of should-be-clear cases with no alert / those runs
- consistency: per case, the share of runs that agree on what was caught, what was wrongly said
  and whether there was any extra alert; then the mean over cases

A number with nothing to count is None, never zero.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from artemis.evaluation.cases import Case


@dataclass(frozen=True)
class AlertMatch:
    title: str
    source: str
    problems: Tuple[str, ...]
    must_not: Tuple[str, ...]


@dataclass(frozen=True)
class RunScore:
    case_id: str
    expect_clear: bool
    has_must_not: bool
    caught: FrozenSet[str]
    missed: FrozenSet[str]
    extra: int
    alerts: int
    must_not_broken: FrozenSet[str]
    matches: Tuple[AlertMatch, ...]


def alert_text(alert: Dict[str, Any]) -> str:
    evidence = alert.get("evidence") or {}
    return " ".join(str(x or "") for x in (alert.get("title"), alert.get("message"), evidence.get("recommended_action")))


def score_run(case: Case, alerts: List[Dict[str, Any]]) -> RunScore:
    matches = []
    for a in alerts:
        text = alert_text(a)
        matches.append(AlertMatch(
            title=str(a.get("title") or ""),
            source=str(a.get("source") or "rule"),
            problems=tuple(p.id for p in case.problems if p.rule.matches(text)),
            must_not=tuple(m.id for m in case.must_not if m.rule.matches(text)),
        ))
    caught = frozenset(pid for m in matches for pid in m.problems)
    return RunScore(
        case_id=case.case_id,
        expect_clear=case.expect_clear,
        has_must_not=bool(case.must_not),
        caught=caught,
        missed=frozenset(p.id for p in case.problems) - caught,
        extra=sum(1 for m in matches if not m.problems),
        alerts=len(matches),
        must_not_broken=frozenset(mid for m in matches for mid in m.must_not),
        matches=tuple(matches),
    )


@dataclass(frozen=True)
class Summary:
    runs: int
    caught: int
    expected: int
    matched_alerts: int
    alerts: int
    clear_correct: int
    clear_runs: int
    must_not_broken_runs: int
    must_not_runs: int
    consistency: Optional[float]

    @staticmethod
    def _share(a: int, b: int) -> Optional[float]:
        return a / b if b else None

    @property
    def sensitivity(self) -> Optional[float]:
        return self._share(self.caught, self.expected)

    @property
    def precision(self) -> Optional[float]:
        return self._share(self.matched_alerts, self.alerts)

    @property
    def specificity(self) -> Optional[float]:
        return self._share(self.clear_correct, self.clear_runs)


def summarize(scores: List[RunScore]) -> Summary:
    by_case: Dict[str, List[RunScore]] = defaultdict(list)
    for s in scores:
        by_case[s.case_id].append(s)
    agree = []
    for runs in by_case.values():
        signatures = Counter((s.caught, s.must_not_broken, s.extra > 0) for s in runs)
        agree.append(signatures.most_common(1)[0][1] / len(runs))
    clear = [s for s in scores if s.expect_clear]
    sick = [s for s in scores if not s.expect_clear]
    guarded = [s for s in scores if s.has_must_not]
    return Summary(
        runs=len(scores),
        caught=sum(len(s.caught) for s in sick),
        expected=sum(len(s.caught) + len(s.missed) for s in sick),
        matched_alerts=sum(s.alerts - s.extra for s in scores),
        alerts=sum(s.alerts for s in scores),
        clear_correct=sum(1 for s in clear if s.alerts == 0),
        clear_runs=len(clear),
        must_not_broken_runs=sum(1 for s in guarded if s.must_not_broken),
        must_not_runs=len(guarded),
        consistency=sum(agree) / len(agree) if agree else None,
    )
