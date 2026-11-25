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
    seconds = [float(r["seconds"]) for r in runs if r.get("seconds") is not None]
    costs = [r.get("cost_usd") for r in runs]
    known = [float(c) for c in costs if c is not None]
    cost = f"${sum(known):.2f}" + ("" if len(known) == len(costs) else " (some unknown)")
    return {
        "citations": _pct(shown, cited),
        "read": _pct(sum(1 for s in screened if s in READ_IN_FULL), len(screened)),
        "seconds": f"{statistics.median(seconds):.1f}" if seconds else "n/a",
        "cost": cost,
    }


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
        "| Model | Runs | Problems caught | Alerts that were real | Clear cases left clear | Must-not broken | "
        "Same answer across runs | Citations to passages shown | Replies read in full | Median seconds | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    listing = ["# Phase 2 matches (preliminary)", "", "Every alert, and the expected problem it matched.", ""]
    for model, runs in models.items():
        scores: List[RunScore] = []
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
            f"| {model} | {s.runs} | {_pct(s.caught, s.expected)} | {_pct(s.matched_alerts, s.alerts)} | "
            f"{_pct(s.clear_correct, s.clear_runs)} | {must_not} | {consistency} | {lf['citations']} | {lf['read']} | "
            f"{lf['seconds']} | {lf['cost']} |"
        )
    return "\n".join(table) + "\n", "\n".join(listing) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases")
    ap.add_argument("--runs", type=Path, default=ROOT / "eval" / "phase2" / "runs")
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "phase2" / "results.md")
    args = ap.parse_args(argv)
    cases = load_cases(args.cases)
    unkeyed = [c.case_id for c in cases if c.key_status == NO_KEY]
    if unkeyed:
        raise SystemExit(f"no answer key yet for: {', '.join(unkeyed)}")
    table, listing = build(cases, _load_runs(args.runs))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(table, encoding="utf-8")
    (args.out.parent / "matches.md").write_text(listing, encoding="utf-8")
    print(f"wrote {args.out} and matches.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
