"""One-time conversion of cases saved with the old add-case form (Phase 1 fix 5).

The old form stored the regimen as typed text and split "Other medications" on commas. For
each case this script:
- turns the regimen into drug codes, keeping the text as written in `art_regimen_as_entered`
- drops "Other medications" entries that only say there are none ("None", "Nil")
- moves entries that name antiretrovirals (a past regimen typed in the wrong box) into the
  history, marked as moved, so nothing written is lost

Running it again changes nothing. The file is written to a temporary name and then renamed.

    python scripts/convert_old_cases.py                       # Data/custom_patients.json
    python scripts/convert_old_cases.py path/to/cases.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artemis.patient.medicines import other_medicines, regimen_codes  # noqa: E402

MOVED_MARK = "Previous ART (moved from Other Medications on 2026-11-25):"


def convert_case(case: Dict[str, Any]) -> Dict[str, Any]:
    case = json.loads(json.dumps(case))  # work on a copy
    raw = [s for s in case.get("art_regimen_current") or [] if isinstance(s, str)]
    codes = regimen_codes(raw)
    if raw and [s.strip() for s in raw] != codes:
        case.setdefault("art_regimen_as_entered", ", ".join(s.strip() for s in raw if s.strip()))
        case["art_regimen_current"] = codes

    meds = case.get("other_medications") or []
    past_art = [m.strip() for m in meds if isinstance(m, str) and m.strip() and regimen_codes([m])]
    case["other_medications"] = [m for m in other_medicines(meds) if m not in past_art]
    if past_art:
        line = f"{MOVED_MARK} {', '.join(past_art)}"
        intake = case.setdefault("intake", {})
        if MOVED_MARK not in (intake.get("prior_history") or ""):
            intake["prior_history"] = "\n\n".join(x for x in [intake.get("prior_history") or "", line] if x)
        for visit in case.get("visits") or []:
            if visit.get("type") == "intake" and MOVED_MARK not in (visit.get("clinician_note") or ""):
                visit["clinician_note"] = "\n\n".join(x for x in [visit.get("clinician_note") or "", line] if x)
    return case


def convert_file(path: Path) -> List[str]:
    """Convert every case in the file; return the ids that changed."""
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    converted = [convert_case(c) for c in cases]
    changed = [c["patient_id"] for c, n in zip(cases, converted) if c != n]
    if changed:
        tmp = Path(str(path) + ".tmp")
        tmp.write_text(json.dumps(converted, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    return changed


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Data" / "custom_patients.json"
    print("changed:", convert_file(target) or "nothing")
