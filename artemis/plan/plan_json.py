"""Reading and checking the management plan the AI returns as JSON.

One copy, used by the AI step (artemis/plan/flow.py) and by the screen (artemis/plan/view.py).
Before fix 7 each had its own copy of the extraction code.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

REGIMEN_DECISIONS = {"Switch", "Hold temporarily", "Continue", "Uncertain"}
VERDICTS = {"Agree", "Disagree", "Gap", "Not Addressed"}


def strip_code_fences(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.splitlines()
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def closing_index(raw: str, pos: int) -> Optional[int]:
    """Where the bracketed JSON value at pos closes, or None when the text ends first. Brackets
    inside strings don't count. From inside a list or object, it's where that one closes. The
    one bracket scanner for the AI's replies: the alert list (artemis/ai/screening.py) and the
    plan (plan item 4.6)."""
    depth, in_str, esc = 0, False, False
    for i in range(pos, len(raw)):
        ch = raw[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth <= 0:
                return i
    return None


def first_json_object(text: str) -> str:
    """The first complete {...} block in the text, ignoring any words around it."""
    raw = strip_code_fences(text)
    start = raw.find("{")
    if start == -1:
        return ""
    end = closing_index(raw, start)
    return raw[start : end + 1] if end is not None else raw[start:]


def loads_relaxed(text: str) -> Any:
    """json.loads, then a second try after repairing common slips (trailing commas, quotes)."""
    try:
        return json.loads(text)
    except ValueError:
        t = re.sub(r",\s*([}\]])", r"\1", text)
        t = re.sub(r"([\{\[,]\s*)'([^']+)'\s*:\s*", r'\1"\2": ', t)
        t = re.sub(r"([\{\[,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)\s*:", r'\1"\2":', t)
        t = re.sub(r":\s*'([^']*)'", r': "\1"', t)
        t = re.sub(r"\[\s*'([^']*)'", r'["\1"', t)
        t = re.sub(r",\s*'([^']*)'", r', "\1"', t)
        return json.loads(t)


def parse_plan(text: str) -> Optional[Dict[str, Any]]:
    """The plan as a dict, or None when the text holds no readable JSON object."""
    raw = first_json_object(text or "")
    if not raw:
        return None
    try:
        obj = loads_relaxed(raw)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def regimen_decision_kind(decision: str) -> str:
    """'Switch', 'Hold temporarily', 'Continue' or 'Uncertain', read from the AI's wording."""
    d = (decision or "").strip().lower()
    if d == "switch":
        return "Switch"
    if d.startswith("hold"):
        return "Hold temporarily"
    if d == "continue":
        return "Continue"
    return "Uncertain"


def validate_plan(text: str) -> List[str]:
    """What is wrong with the plan, as short codes; an empty list means it passed."""
    if not (text or "").strip():
        return ["empty_output"]
    raw = first_json_object(text)
    if not raw:
        return ["no_json_object_found"]
    try:
        obj = json.loads(raw)
    except ValueError:
        return ["invalid_json"]
    if not isinstance(obj, dict):
        return ["root_not_object"]

    issues: List[str] = []
    for k in ["art_regimen_decision", "problems", "monitoring_plan", "patient_counselling"]:
        if k not in obj:
            issues.append(f"missing_key:{k}")

    ard = obj.get("art_regimen_decision")
    if not isinstance(ard, dict):
        issues.append("art_regimen_decision_wrong_type")
    elif "decision" not in ard or "reason" not in ard:
        issues.append("art_regimen_decision_missing_fields")
    else:
        decision = str(ard.get("decision") or "").strip()
        if decision not in REGIMEN_DECISIONS and not decision.lower().startswith("uncertain"):
            issues.append("art_regimen_decision_bad_decision")
        if not str(ard.get("reason") or "").strip():
            issues.append("art_regimen_decision_empty_reason")

    problems = obj.get("problems")
    if not isinstance(problems, list) or not problems:
        issues.append("problems_not_nonempty_list")
    else:
        seen: set = set()
        for idx, p in enumerate(problems[:10]):
            if not isinstance(p, dict):
                issues.append(f"problem_{idx}_not_object")
                continue
            for k in ["problem", "action", "reason", "clinician_plan_for_this_problem"]:
                if k not in p:
                    issues.append(f"problem_{idx}_missing_key:{k}")
            low = " ".join(str(p.get("problem") or "").strip().lower().split())
            if low.startswith(("assess", "check", "review", "evaluate", "screen", "monitor")):
                issues.append(f"problem_{idx}_looks_like_task")
            if low and low in seen:
                issues.append(f"problem_{idx}_duplicate")
            seen.add(low)
            cp = p.get("clinician_plan_for_this_problem")
            if isinstance(cp, dict):
                if "decision" not in cp or "explanation" not in cp:
                    issues.append(f"problem_{idx}_clinician_plan_missing_fields")
                elif str(cp.get("decision") or "").strip() not in VERDICTS:
                    issues.append(f"problem_{idx}_clinician_plan_bad_decision")
            elif "clinician_plan_for_this_problem" in p:
                issues.append(f"problem_{idx}_clinician_plan_wrong_type")

    if not isinstance(obj.get("monitoring_plan"), (str, list, dict)):
        issues.append("monitoring_plan_wrong_type")
    if not isinstance(obj.get("patient_counselling"), list):
        issues.append("patient_counselling_not_list")
    return issues
