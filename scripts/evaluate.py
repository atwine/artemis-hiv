"""Rebuild the Phase 2 results table from saved runs (nothing is sent to any model).

    python scripts/evaluate.py
    python scripts/evaluate.py --cases eval/cases --runs eval/phase2/runs --out eval/phase2/results.md

Runs are read from <runs>/<model>/<case>__run<k>.json, as the Phase 2 runner writes them. The
table gives, per model, the scores against the draft answer key and the measures that need no
answer key. A second file, matches.md next to the table, lists every alert and what it matched,
so the word rules can be checked by eye. Every number here is preliminary: the answer key is a
draft that the doctor reviews in Phase 7.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artemis.evaluation.afrimedqa import accuracy  # noqa: E402
from artemis.evaluation.cases import NO_KEY, Case, load_cases  # noqa: E402
from artemis.evaluation.scoring import RunScore, score_run, summarize  # noqa: E402

READ_IN_FULL = {"parsed_nonempty", "parsed_empty"}


def _pct(a: int, b: int) -> str:
    return f"{round(100 * a / b)}% ({a}/{b})" if b else "n/a"


def _label_free(runs: List[Dict[str, Any]]) -> Dict[str, str]:
    cited = shown = 0
    for r in runs:
        for a in r.get("alerts") or []:
            for c in (a.get("evidence") or {}).get("citations") or []:
                cited += 1
                shown += 1 if c.get("shown_to_ai") else 0
    screened = [((r.get("screening") or {}).get("parse_status")) for r in runs if r.get("screening")]
    plans = [r.get("plan_issues") or [] for r in runs if r.get("plan_text") is not None]
    seconds = [float(r["seconds"]) for r in runs if r.get("seconds") is not None]
    costs = [r.get("cost_usd") for r in runs]
    known = [float(c) for c in costs if c is not None]
    cost = f"${sum(known):.2f}" + ("" if len(known) == len(costs) else " (some unknown)")
    return {
        "citations": _pct(shown, cited),
        "read": _pct(sum(1 for s in screened if s in READ_IN_FULL), len(screened)),
        "plans": _pct(sum(1 for issues in plans if "cut_off" not in issues), len(plans)),
        "seconds": f"{statistics.median(seconds):.1f}" if seconds else "n/a",
        "cost": cost,
        "per_check": f"${sum(known) / len(known):.4f}" if known else "n/a",
    }


def _per_problem(cases: List[Case], scores: Dict[str, List[RunScore]]) -> List[str]:
    """Runs that caught each expected problem, out of that case's runs, per model."""
    models = list(scores)
    lines = ["", "## Catches per expected problem", "",
             "Runs in which some alert caught the problem, out of that case's runs.", "",
             "| Expected problem | " + " | ".join(models) + " |", "|---|" + "---|" * len(models)]
    for case in cases:
        for p in case.problems:
            cells = []
            for m in models:
                runs = [s for s in scores[m] if s.case_id == case.case_id]
                cells.append(f"{sum(p.id in s.caught for s in runs)}/{len(runs)}")
            lines.append(f"| {case.case_id}: {p.id} | " + " | ".join(cells) + " |")
    return lines


def _load_runs(folder: Path) -> Dict[str, List[Dict[str, Any]]]:
    models: Dict[str, List[Dict[str, Any]]] = {}
    for model_dir in sorted(p for p in folder.iterdir() if p.is_dir()) if folder.exists() else []:
        models[model_dir.name] = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(model_dir.glob("*__run*.json"))]
    return models


def build(cases: List[Case], models: Dict[str, List[Dict[str, Any]]]) -> tuple:
    by_id = {c.case_id: c for c in cases}
    table = [
        "# Phase 2 results (preliminary)",
        "",
        "Scored against a draft answer key that no clinician has checked yet (the doctor reviews it in",
        "Phase 7). These numbers steer the work; they are not the app's accuracy.",
        "",
        "| Model | Runs | Problems caught | Caught by the AI's own alerts | Alerts that were real | "
        "Clear cases left clear | Must-not broken | Same answer across runs | Citations to passages shown | "
        "Alert replies read in full | Plans read in full | Median seconds | Cost | Cost per check |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    listing = ["# Phase 2 matches (preliminary)", "", "Every alert, and the expected problem it matched.", ""]
    all_scores: Dict[str, List[RunScore]] = {}
    for model, runs in models.items():
        scores: List[RunScore] = all_scores.setdefault(model, [])
        listing.append(f"## {model}")
        for r in sorted(runs, key=lambda r: (str(r.get("case_id")), int(r.get("repeat") or 0))):
            case = by_id.get(str(r.get("case_id")))
            if case is None:
                raise SystemExit(f"{model}: a run names an unknown case {r.get('case_id')!r}")
            s = score_run(case, r.get("alerts") or [])
            scores.append(s)
            listing.append(f"- {case.case_id} run {r.get('repeat')}: missed: {', '.join(sorted(s.missed)) or 'none'}"
                           + (f"; must-not broken: {', '.join(sorted(s.must_not_broken))}" if s.must_not_broken else ""))
            for m in s.matches:
                what = ", ".join(m.problems) or (f"also fine: {', '.join(m.also_fine)}" if m.also_fine else "extra")
                listing.append(f"  - [{m.source}] {m.title} -> {what}")
        listing.append("")
        s = summarize(scores)
        lf = _label_free(runs)
        consistency = f"{round(100 * s.consistency)}%" if s.consistency is not None else "n/a"
        must_not = f"{s.must_not_broken_runs}/{s.must_not_runs}" if s.must_not_runs else "n/a"
        table.append(
            f"| {model} | {s.runs} | {_pct(s.caught, s.expected)} | {_pct(s.caught_by_ai, s.expected)} | "
            f"{_pct(s.matched_alerts, s.alerts)} | {_pct(s.clear_correct, s.clear_runs)} | {must_not} | {consistency} | "
            f"{lf['citations']} | {lf['read']} | {lf['plans']} | {lf['seconds']} | {lf['cost']} | {lf['per_check']} |"
        )
    if all_scores:
        table += _per_problem(cases, all_scores)
    return "\n".join(table) + "\n", "\n".join(listing) + "\n"


def quiz_table(folder: Path) -> str:
    """The AfriMed-QA table: share of multiple-choice questions answered exactly right, per model."""
    files = sorted(folder.glob("*.jsonl")) if folder.exists() else []
    if not files:
        return ""
    lines = [
        "", "## AfriMed-QA knowledge check", "",
        "Exam-style multiple-choice questions on infectious disease or HIV (AfriMed-QA v2). This tests what",
        "a model knows, not the app's job; it only helps narrow the models.", "",
        "| Model | All questions | HIV-related | Infectious disease | Cost |", "|---|---|---|---|---|",
    ]
    for f in files:
        rows = [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
        acc = accuracy(rows)
        cost = sum(float(r.get("cost_usd") or 0) for r in rows)
        lines.append(f"| {f.stem} | {_pct(*acc['all'])} | {_pct(*acc['hiv'])} | {_pct(*acc['infectious_disease'])} | "
                     f"${cost:.2f} |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases")
    ap.add_argument("--runs", type=Path, default=ROOT / "eval" / "phase2" / "runs")
    ap.add_argument("--quiz", type=Path, default=ROOT / "eval" / "phase2" / "afrimedqa")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "phase2" / "results.md")
    args = ap.parse_args(argv)
    cases = load_cases(args.cases)
    unkeyed = [c.case_id for c in cases if c.key_status == NO_KEY]
    if unkeyed:
        raise SystemExit(f"no answer key yet for: {', '.join(unkeyed)}")
    table, listing = build(cases, _load_runs(args.runs))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(table + quiz_table(args.quiz), encoding="utf-8")
    (args.out.parent / "matches.md").write_text(listing, encoding="utf-8")
    print(f"wrote {args.out} and matches.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
