"""Freeze the test patients into evaluation case files (Phase 2).

    python scripts/make_cases.py

Writes eval/cases/<case>.json for each patient in Data/mock_patients.json and
Data/custom_patients.json that has no case file yet. Existing case files, and the answer keys
in them, are never touched, so running it twice changes nothing.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from artemis.evaluation.cases import case_file_name  # noqa: E402

SOURCES = {"mock_patients.json": "test patient (Data/mock_patients.json)",
           "custom_patients.json": "test patient (Data/custom_patients.json)"}


def main() -> int:
    out = ROOT / "eval" / "cases"
    out.mkdir(parents=True, exist_ok=True)
    written = 0
    for name, source in SOURCES.items():
        for patient in json.loads((ROOT / "Data" / name).read_text(encoding="utf-8")):
            path = out / case_file_name(str(patient["patient_id"]))
            if path.exists():
                continue
            case = {"case_id": patient["patient_id"], "source": source, "patient": patient}
            fd, tmp = tempfile.mkstemp(dir=out, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(case, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            written += 1
    print(f"{written} case file(s) written to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
