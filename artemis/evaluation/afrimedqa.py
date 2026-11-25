"""AfriMed-QA knowledge check (Phase 2): exam-style multiple-choice questions, not the app's task.

Uses the multiple-choice questions that are infectious disease or mention HIV, from the
AfriMed-QA v2 file (Nimo, Olatunji et al., ACL 2025; Hugging Face intronhealth/afrimedqa_v2,
downloaded to eval/afrimedqa/data/, never committed). A question counts as right only when the
model names exactly the correct option keys. Saved results hold question ids and the model's
answers, never the question text.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

HIV = re.compile(r"\bhiv\b|antiretrovir|\bart\b|\barvs?\b|\bcd4\b|viral load|tenofovir|dolutegravir|efavirenz|"
                 r"zidovudine|lamivudine|nevirapine|pmtct|\baids\b", re.IGNORECASE)


@dataclass(frozen=True)
class Question:
    sample_id: str
    text: str
    options: Dict[str, str]
    correct: FrozenSet[str]
    specialty: str
    tier: str
    hiv: bool


def load_questions(path: Path) -> List[Question]:
    out: List[Question] = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("question_type") or "").strip().lower() != "mcq":
                continue
            text = (row.get("question_clean") or row.get("question") or "").strip()
            try:
                options = json.loads(row.get("answer_options") or "{}")
            except json.JSONDecodeError:
                continue
            if not text or not isinstance(options, dict) or not options:
                continue
            is_hiv = bool(HIV.search(text + " " + " ".join(str(v) for v in options.values())))
            specialty = str(row.get("specialty") or "")
            if not (is_hiv or "infectious" in specialty.lower()):
                continue
            correct = frozenset(k.strip() for k in str(row.get("correct_answer") or "").split(",") if k.strip())
            out.append(Question(str(row["sample_id"]), text, {str(k): str(v) for k, v in options.items()},
                                correct, specialty, str(row.get("tier") or ""), is_hiv))
    return out


def messages(q: Question) -> List[Dict[str, str]]:
    # Saying how many to pick, as exam papers do, keeps "which is a complication of hepatitis B?"
    # (every option is one) a knowledge question instead of a guess at what the setter meant.
    n = len(q.correct)
    pick = "Choose the single best option." if n == 1 else f"Choose exactly {n} options."
    system = (f"You answer multiple-choice medical questions. {pick} Reply with only the option key, "
              'as JSON, for example {"answer": ["option2"]}.')
    listed = "\n".join(f"{k}: {v}" for k, v in q.options.items())
    return [{"role": "system", "content": system}, {"role": "user", "content": f"{q.text}\n\n{listed}"}]


def answer_format(q: Question) -> Dict[str, Any]:
    """The reply format: the right number of option keys, each one of the question's own."""
    n = len(q.correct)
    keys = {"type": "array", "items": {"type": "string", "enum": sorted(q.options)}, "minItems": n, "maxItems": n}
    return {"type": "object", "properties": {"answer": keys}, "required": ["answer"]}


def read_answer(reply: Optional[str]) -> Set[str]:
    return {f"option{n}" for n in re.findall(r"option\s*(\d)", reply or "", re.IGNORECASE)}


def score(q: Question, answer: Set[str]) -> bool:
    return bool(answer) and set(answer) == set(q.correct)


def answered_ids(path: Path) -> Set[str]:
    if not Path(path).exists():
        return set()
    ids = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            ids.add(str(json.loads(line)["sample_id"]))
        except (ValueError, KeyError):
            continue
    return ids


def result_row(q: Question, reply: Optional[str], cost: float) -> Dict[str, Any]:
    """One saved answer. The reply is kept only when no option could be read from it, to check the reader."""
    answer = read_answer(reply)
    return {"sample_id": q.sample_id, "hiv": q.hiv, "specialty": q.specialty, "tier": q.tier,
            "answer": sorted(answer), "correct": sorted(q.correct), "right": score(q, answer),
            "unread_reply": None if answer else (reply or "")[:80], "cost_usd": cost}


def accuracy(rows: List[Dict[str, Any]]) -> Dict[str, Tuple[int, int]]:
    """(right, asked) for all questions, the HIV-related ones and the infectious-disease ones."""
    groups = {"all": rows, "hiv": [r for r in rows if r["hiv"]],
              "infectious_disease": [r for r in rows if "infectious" in str(r["specialty"]).lower()]}
    return {name: (sum(bool(r["right"]) for r in rs), len(rs)) for name, rs in groups.items()}
