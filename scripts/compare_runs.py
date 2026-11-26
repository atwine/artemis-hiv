"""Compare two folders written by scripts/run_baseline.py, patient by patient.

    python scripts/compare_runs.py eval/baseline eval/after-phase1 > eval/after-phase1/compare.md

Answers vary between runs, so each measure is shown as the list of values across that
folder's runs, and a measure counts as changed only when those lists differ. A patient
present in only one folder is reported, never skipped. Exit code: 0 when nothing changed,
1 when something did, 2 when a folder has no runs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from artemis.statuses import status_name  # noqa: E402  (no heavy imports)

Run = Dict[str, Any]


def load(folder: Path) -> Dict[str, List[Run]]:
    runs: Dict[str, List[Run]] = {}
    for f in sorted(folder.glob("*__run*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        runs.setdefault(str(d["patient_id"]), []).append(d)
    for rs in runs.values():
        rs.sort(key=lambda r: r.get("repeat", 0))
    return runs


def _doc(path: str) -> str:
    return re.split(r"[\\/]", path or "?")[-1]


def _sources(r: Run) -> str:
    c = Counter(
        _doc(ch.get("metadata", {}).get("source_path", "?"))
        for res in r.get("results") or []
        for ch in res.get("retrieved") or []
    )
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items())) or "none"


MEASURES: Dict[str, Callable[[Run], Any]] = {
    # Older runs say YELLOW for what is now AMBER (owner, 2026-11-26): the same result.
    "status": lambda r: status_name(r.get("overall_status")),
    "alerts": lambda r: len(r.get("alerts") or []),
    "rule alerts": lambda r: len(r.get("rule_alerts") or []),
    "rule alerts kept on screen": lambda r: sum(
        1
        for a in r.get("alerts") or []
        if (a.get("evidence") or {}).get("type") != "llm_screening"
    ),
    "plan items": lambda r: len(r.get("plan_items") or []),
    "plan items with no model verdict": lambda r: sum(
        1 for i in r.get("plan_items") or [] if not i.get("model_decision")
    ),
    "llm error": lambda r: bool(r.get("llm_error")),
    "retrieved passages by document": _sources,
}


def compare(before: Dict[str, List[Run]], after: Dict[str, List[Run]]) -> tuple:
    lines: List[str] = ["# Run comparison", ""]
    changed = 0
    for pid in sorted(set(before) | set(after)):
        lines.append(f"## {pid}")
        if pid not in before or pid not in after:
            lines += [f"- only in {'after' if pid in after else 'before'}", ""]
            changed += 1
            continue
        b, a = before[pid], after[pid]
        lines.append(f"- runs: {len(b)} before, {len(a)} after")
        for name, fn in MEASURES.items():
            bv, av = [fn(r) for r in b], [fn(r) for r in a]
            if bv == av:
                lines.append(f"- {name}: same ({bv})")
            else:
                changed += 1
                lines.append(f"- **{name}: changed** {bv} -> {av}")
        bt = sorted({x.get("title", "") for r in b for x in r.get("alerts") or []})
        at = sorted({x.get("title", "") for r in a for x in r.get("alerts") or []})
        if bt != at:
            lines.append(f"- alert titles gone: {[t for t in bt if t not in at]}")
            lines.append(f"- alert titles new: {[t for t in at if t not in bt]}")
        lines.append("")
    lines.insert(1, f"{changed} change(s) across {len(set(before) | set(after))} patient(s).")
    return "\n".join(lines) + "\n", changed


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("before", type=Path)
    ap.add_argument("after", type=Path)
    args = ap.parse_args(argv)
    before, after = load(args.before), load(args.after)
    if not before or not after:
        print(f"no runs in {args.before if not before else args.after}; refusing to compare")
        return 2
    report, changed = compare(before, after)
    sys.stdout.write(report)
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(main())
