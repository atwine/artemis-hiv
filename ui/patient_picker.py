"""How a patient is named in the patient list."""

from __future__ import annotations

from typing import Any, Dict


def patient_label(patient: Dict[str, Any]) -> str:
    """'P001 - John Doe', or just the id when the record has no name (cases added on screen)."""
    pid = str(patient.get("patient_id") or "")
    name = str(patient.get("name") or "").strip()
    return f"{pid} - {name}" if name else pid
