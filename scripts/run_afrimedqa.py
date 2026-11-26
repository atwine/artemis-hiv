"""Ask one model the AfriMed-QA infectious-disease and HIV multiple-choice questions.

    python scripts/run_afrimedqa.py --model llama-a100
    python scripts/run_afrimedqa.py --model glm-5.2 --limit 3
    python scripts/run_afrimedqa.py --model deepseek-v3.2 --dry-run

Needs the AfriMed-QA file in eval/afrimedqa/data/ (gitignored). Answers go to
eval/phase2/afrimedqa/<model>.jsonl, one line per question: its id, the model's answer, the
right answer and the cost, never the question text. Answered questions are skipped, so a
stopped run resumes. Temperature 0. The spend across everything under eval/phase2 is checked
before the run (a worst-case estimate must fit under --cap) and after every question.
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

from run_phase2 import MARGIN, PRESETS, model_config  # noqa: E402

from artemis.ai.client import OpenAICompatClient  # noqa: E402
from artemis.evaluation.afrimedqa import answer_format, answered_ids, load_questions, messages, result_row  # noqa: E402
from artemis.evaluation.runner import BudgetExceeded, check_budget, cost_of, spent_in  # noqa: E402

DATA = ROOT / "eval" / "afrimedqa" / "data" / "afri_med_qa_15k_v2.4_phase_2_15275.csv"
MAX_TOKENS = 40  # {"answer": ["option1", "option3"]} is about 15 tokens
CHARS_PER_TOKEN = 3  # a low guess, so the worst case runs high


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, choices=sorted(PRESETS))
    ap.add_argument("--data", type=Path, default=DATA)
    ap.add_argument("--limit", type=int, default=None, help="ask only this many unanswered questions")
    ap.add_argument("--cap", type=float, default=5.0, help="dollars, across everything under eval/phase2")
    ap.add_argument("--root", type=Path, default=ROOT / "eval" / "phase2")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    out = args.root / "afrimedqa" / f"{args.model}.jsonl"
    done = answered_ids(out)
    todo = [q for q in load_questions(args.data) if q.sample_id not in done][: args.limit]

    config, price_in, price_out = model_config(args.model, 0.0)

    def worst_for(q) -> float:
        return (len(json.dumps(messages(q))) / CHARS_PER_TOKEN * price_in + MAX_TOKENS * price_out) * MARGIN

    worst = sum(worst_for(q) for q in todo)
    spent = spent_in(args.root)
    print(f"{args.model}: {len(todo)} questions to ask ({len(done)} answered); worst case ${worst:.2f}; "
          f"${spent:.4f} spent so far; cap ${args.cap:.2f}")
    try:
        check_budget(spent=spent, checks=1, per_check=worst, cap=args.cap)
    except BudgetExceeded as exc:
        raise SystemExit(f"refused: {exc}")
    if args.dry_run or not todo:
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not out.read_bytes().endswith(b"\n") and out.stat().st_size:
        with out.open("a", encoding="utf-8") as fh:
            fh.write("\n")  # a line cut off by a crash stays on its own line and is skipped
    client = OpenAICompatClient(config)
    right = 0
    for i, q in enumerate(todo, 1):
        try:
            check_budget(spent=spent, checks=1, per_check=worst_for(q), cap=args.cap)
        except BudgetExceeded:
            print(f"stopped before question {q.sample_id}: one more could pass the ${args.cap:.2f} cap")
            return 1
        reply = client.chat(messages(q), format=answer_format(q), options_override={"num_predict": MAX_TOKENS})
        if reply.text is None and reply.error:
            # Not saved: a server outage is not an answer, and a saved one would be skipped on resume.
            print(f"stopped at question {q.sample_id}: {reply.error}; nothing saved for it")
            return 2
        row = result_row(q, reply.text, cost_of([reply.usage], price_in, price_out))
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        spent += row["cost_usd"]
        right += row["right"]
        if i % 25 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)} asked, {right} right, total ${spent:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
