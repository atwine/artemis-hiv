"""Was each problem's guideline passage in front of the AI, and did the AI catch it anyway? (Phase 2B)

    python scripts/diagnose_search.py > eval/phase2b/diagnosis.md

Reads the saved Phase 2 runs; no AI call. "Shown" means the gold quote is in the passages the AI
screening read, as cut for it (480 characters each). "Caught" counts the AI's own alerts only,
not the fixed rules, which are the same whichever model runs.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artemis.evaluation.cases import load_cases  # noqa: E402
from artemis.evaluation.retrieval import case_items, first_hit  # noqa: E402
from artemis.evaluation.scoring import score_run  # noqa: E402

MODELS = {"llama-a100-t0": "Llama", "glm-5.2": "GLM", "deepseek-v3.2": "DeepSeek", "claude-haiku-5.5": "Haiku"}


def main() -> int:
    cases = {c.case_id: c for c in load_cases(ROOT / "eval" / "cases")}
    shown = collections.defaultdict(set)
    caught = collections.defaultdict(collections.Counter)
    runs = collections.defaultdict(collections.Counter)
    for folder, name in MODELS.items():
        for f in sorted((ROOT / "eval" / "phase2" / "runs" / folder).glob("*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            case = cases[r["case_id"]]
            bundle = [b.get("quote") or "" for b in (r.get("screening") or {}).get("screening_bundle") or []]
            s = score_run(case, r.get("alerts") or [])
            for item in case_items(case):
                pid = item.item_id.split(":", 1)[1]
                if item.gold:
                    shown[item.item_id].add(first_hit(bundle, item.gold) is not None)
                runs[item.item_id][name] += 1
                caught[item.item_id][name] += pid in s.caught_by_ai

    print("# Search diagnosis: was the passage shown, and was the problem caught?\n")
    print("From the saved Phase 2 runs (Llama at temperature 0, the others at 0.2). Catches count the AI's own alerts.\n")
    print("| Problem | Gold passage shown to the AI | " + " | ".join(MODELS.values()) + " |")
    print("|---|---|" + "---|" * len(MODELS))
    tally: collections.Counter = collections.Counter()
    for case in cases.values():
        for item in case_items(case):
            seen = shown[item.item_id]
            label = "not in the guidelines" if not item.gold else ("yes" if seen == {True} else "no" if seen == {False} else "sometimes")
            print(f"| {item.item_id} | {label} | " + " | ".join(f"{caught[item.item_id][n]}/{runs[item.item_id][n]}" for n in MODELS.values()) + " |")
            for n in MODELS.values():
                tally[(label, True)] += caught[item.item_id][n]
                tally[(label, False)] += runs[item.item_id][n] - caught[item.item_id][n]
    print()
    for label in ("yes", "no", "sometimes", "not in the guidelines"):
        c, m = tally[(label, True)], tally[(label, False)]
        if c + m:
            print(f"- Passage shown: {label}. The AI caught {c} of {c + m} problem-runs ({round(100 * c / (c + m))}%).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
