"""Check the guideline search: does the passage each problem rests on come back? (Phase 2B)

    python scripts/check_retrieval.py --label baseline
    python scripts/check_retrieval.py --label 5q-ai-questions --ai llama-a100

Without --ai no AI is called and the generic screening search is checked. For each case it runs the search the app's AI screening reads
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
from artemis.ai.client import ChatReply, OpenAICompatClient  # noqa: E402
from artemis.visit import AnalysisOptions, patient_context_for, patient_summary_for, screening_search  # noqa: E402
from run_phase2 import PRESETS, model_config  # noqa: E402

DEPTH = 10  # passages checked; the app shows the AI AnalysisOptions().top_k of them


class _Recorder:
    """Keeps the error of the last reply it passed on, so a failed AI call stops the check."""

    def __init__(self, client) -> None:
        self._client, self.last_error, self.model = client, None, getattr(client, "model", "?")

    def chat(self, *args, **kwargs):
        reply = self._client.chat(*args, **kwargs)
        self.last_error = reply.error
        return reply


class _Replay:
    """Answers the question step with the questions saved for each case, in the app's own format."""

    model = "replay"

    def __init__(self, saved: dict) -> None:
        self._saved = saved

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        facts = str(messages[-1]["content"])
        case_id = next(cid for cid in self._saved if f"Patient ID: {cid}\n" in facts)
        return ChatReply(json.dumps(self._saved[case_id] or []), finish_reason="stop")


def _note(case) -> str:
    return (case.patient.get("today_encounter") or {}).get("note") or ""


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", default="baseline", help="names the variant being measured")
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases")
    ap.add_argument("--questions", type=Path, default=ROOT / "eval" / "phase2b" / "questions.json")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--replay-questions", type=Path, default=None,
                    help="replay the AI questions saved in an earlier search-*.json instead of asking an AI")
    ap.add_argument("--ai", choices=sorted(PRESETS), default=None,
                    help="let this model write the patient's guideline questions first, as the app does")
    args = ap.parse_args(argv)

    rag = rb.app._get_rag_engine(prefer_chroma=True, embedding_model_name=rb.app.EMBEDDING_MODEL, engine_version=5)
    if not rag.search_ready:
        # The app falls back to word hashing when the model can't load (G33); a measurement must not.
        raise SystemExit(f"the search model {rb.app.EMBEDDING_MODEL} did not load; nothing measured")
    if rb.app.GUIDELINE_PATHS:
        rag.ensure_indexed()
    cases = load_cases(args.cases)
    questions = load_search_questions(args.questions)
    allowed = {p.stem for p in rb.app.GUIDELINE_PATHS}  # what the app searches: Ugandan guidance only
    if args.replay_questions:
        # The questions an AI wrote in an earlier check, replayed, so only the index changes.
        ai = _Recorder(_Replay(json.loads(args.replay_questions.read_text(encoding="utf-8"))["search_questions"]))
    else:
        ai = _Recorder(OpenAICompatClient(model_config(args.ai, None)[0])) if args.ai else None
    asked = {}

    def case_search(c):
        context = patient_context_for(c.patient, _note(c))
        if ai is None:
            return screening_search(rag, context, DEPTH).passages
        found = screening_search(rag, context, AnalysisOptions().top_k, llm_client=ai,
                                 summary=patient_summary_for(c.patient, _note(c)))
        asked[c.case_id] = found.questions
        if ai.last_error:
            # The app may fall back to the generic search, but a check of the AI's questions must not:
            # a fallback would measure the old search under the new label.
            raise SystemExit(f"stopped at {c.case_id}: the AI call failed ({ai.last_error}); nothing written")
        return found.passages

    rows = check_search(
        cases, questions,
        case_search=case_search,
        question_search=lambda text: rag.search(text, top_k=DEPTH),
        allowed=allowed,
        ideal_search=lambda text: rag.search(text, top_k=DEPTH),
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
                               "ai": args.ai, "search_questions": asked,
                               "self_check": {"found": sane, "of": len(gold),
                                              "missed": [vars(g) for g in misses]}, "rows": rows},
                              ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    for r in rows:
        rank = "not in the searched guidelines" if not r["covered"] else (f"rank {r['rank']}" if r["rank"] else "not found")
        top = ", ".join(s.replace(".extraction", "") for s in r["sources"][:shown])
        print(f"{r['item']:<38} {rank:<22} top {shown}: {top}")
    seen = sum(1 for r in rows if r["kind"] == "case" and r["covered"] and r["rank"] is not None
               and (ai is not None or r["rank"] <= shown))
    print(f"{args.label} cases: the right passage is among the passages the AI sees for {seen}/{summary['case'].covered}")
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
