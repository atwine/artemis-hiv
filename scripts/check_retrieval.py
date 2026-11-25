"""Check the guideline search: does the passage each problem rests on come back? (Phase 2B)

    python scripts/check_retrieval.py --label baseline

No AI is called; it takes seconds. For each case it runs the search the app's AI screening reads
(artemis.visit.screening_search) and looks for each expected problem's gold quote in the top 10
passages; the app shows the AI the top 5. Each standalone question in eval/phase2b/questions.json
is searched as written. Writes eval/phase2b/search-<label>.json and prints the table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_baseline as rb  # noqa: E402  (builds the app's own guideline index)

from artemis.evaluation.cases import load_cases  # noqa: E402
from artemis.evaluation.retrieval import (case_items, check_search, load_search_questions, self_check,  # noqa: E402
                                          summarize_check)
from artemis.visit import AnalysisOptions, patient_context_for, screening_search  # noqa: E402

DEPTH = 10  # passages checked; the app shows the AI AnalysisOptions().top_k of them


def _note(case) -> str:
    return (case.patient.get("today_encounter") or {}).get("note") or ""


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", default="baseline", help="names the variant being measured")
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases")
    ap.add_argument("--questions", type=Path, default=ROOT / "eval" / "phase2b" / "questions.json")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    rag = rb.app._get_rag_engine(prefer_chroma=True, embedding_model_name="all-MiniLM-L6-v2", engine_version=5)
    if rb.app.GUIDELINE_PDF_PATHS:
        rag.ensure_indexed()
    cases = load_cases(args.cases)
    questions = load_search_questions(args.questions)
    allowed = {p.stem for p in rb.app.GUIDELINE_PATHS}  # what the app searches: Ugandan guidance only
    rows = check_search(
        cases, questions,
        case_search=lambda c: screening_search(rag, patient_context_for(c.patient, _note(c)), DEPTH),
        question_search=lambda text: rag.search(text, top_k=DEPTH),
        allowed=allowed,
    )
    shown = AnalysisOptions().top_k
    summary = summarize_check(rows)
    gold = ([g for c in cases for i in case_items(c, allowed) for g in i.gold]
            + [g for i, _ in questions for g in i.gold if g.document in allowed])
    sane, misses = self_check(gold, lambda text: rag.search(text, top_k=DEPTH))
    out = args.out or ROOT / "eval" / "phase2b" / f"search-{args.label}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"label": args.label, "depth": DEPTH, "shown_to_ai": shown,
                               "summary": {k: vars(v) for k, v in summary.items()},
                               "self_check": {"found": sane, "of": len(gold),
                                              "missed": [vars(g) for g in misses]}, "rows": rows},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    for r in rows:
        rank = "not in the searched guidelines" if not r["covered"] else (f"rank {r['rank']}" if r["rank"] else "not found")
        top = ", ".join(s.replace(".extraction", "") for s in r["sources"][:shown])
        print(f"{r['item']:<38} {rank:<22} top {shown}: {top}")
    for kind, s in summary.items():
        mrr = f"{s.mrr:.2f}" if s.mrr is not None else "n/a"
        print(f"{args.label} {kind}s: found in the top {shown} {s.found_in_5}/{s.covered}, top 10 {s.found_in_10}/{s.covered}, "
              f"MRR {mrr}; {s.not_covered} not in the searched guidelines")
    print(f"self-check: {sane}/{len(gold)} gold quotes come back when searched word for word")
    for g in misses:
        print(f"  not back: {g.document} | {g.quote[:90]}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
