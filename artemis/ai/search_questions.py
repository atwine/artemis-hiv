"""The AI lists the patient's own guideline questions before the screening (Phase 2B fix 5q).

The screening used to search the guidelines with one fixed phrase plus the whole note, so most
patients got the same passages. Searching each problem by its own description found the right
Ugandan passage far more often (the Phase 2B premise check), so the AI first writes those
questions from the patient facts, and the app searches each one.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional

MAX_QUESTIONS = 6
MAX_LENGTH = 200

_INSTRUCTIONS = (
    "You help an HIV clinician in Uganda check a visit for medication-safety problems. From the "
    "patient facts, write up to 6 short questions to look up in the Uganda HIV guidelines: side "
    "effects or toxicity the labs or symptoms may show, interactions between the HIV drugs and the "
    "patient's other medicines, monitoring tests that are due or overdue, and pregnancy or other "
    "conditions that change the treatment. One question per problem, in plain words, under 15 "
    "words each. Reply with a JSON array of strings only."
)
_FORMAT = {"type": "array", "items": {"type": "string"}, "maxItems": MAX_QUESTIONS}


def ask_search_questions(llm_client: Any, facts: str) -> List[str]:
    """Up to 6 short questions about this patient, or [] when the AI gives nothing usable. `facts` is
    the patient text the screening reads too (artemis.ai.screening.patient_facts)."""
    messages = [
        {"role": "system", "content": _INSTRUCTIONS},
        {"role": "user", "content": facts},
    ]
    reply = llm_client.chat(messages, format=_FORMAT, options_override={"num_predict": 300}).text
    try:
        items = json.loads(reply or "")
    except ValueError:
        return []
    if not isinstance(items, list):
        return []
    questions = [" ".join(str(q).split())[:MAX_LENGTH] for q in items if isinstance(q, str) and q.strip()]
    return list(dict.fromkeys(questions))[:MAX_QUESTIONS]
