"""The visit record (fix 9): what was checked, what the screen showed, and what the clinician decided.

One file per patient, in a folder git ignores (Data/visit_records unless the
ARTEMIS_VISIT_RECORDS_DIR setting says otherwise). Each line is one event, written once and
never changed:
- "checks_run", written when the checks run. It holds the note, the alerts and everything the
  screen showed, so the results can be reopened without asking the AI again (fix 9b).
- "finalized", written at Finalize. It holds the clinician's decision on each alert.
The full-stack rebuild moves these records into Postgres (plan item 4.5).
"""

from __future__ import annotations

import datetime
import functools
import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from artemis.plan.flow import AgenticResult
from artemis.rules.checks import Alert
from modules.explanation_generator import ExplanationResult
from artemis.guidelines.vector_store import VectorSearchResult

RECORDS_ENV = "ARTEMIS_VISIT_RECORDS_DIR"

Entry = Dict[str, Any]


def records_dir(project_root: Path) -> Path:
    return Path(os.getenv(RECORDS_ENV) or project_root / "Data" / "visit_records")


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


@functools.lru_cache(maxsize=4)
def app_version(project_root: Path) -> str:
    """The code version saved with each record: the git commit, or "unknown"."""
    try:
        out = subprocess.run(
            ["git", "describe", "--always", "--dirty"],
            cwd=project_root, capture_output=True, text=True, timeout=5, check=True,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _file_name(patient_id: str) -> str:
    """A safe file name for any patient id. The hash keeps look-alike ids ("a b", "a_b") apart."""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", patient_id)[:40] or "patient"
    return f"{safe}_{hashlib.sha1(patient_id.encode('utf-8')).hexdigest()[:10]}.jsonl"


def _plan(agentic: Any) -> Any:
    if agentic is None or isinstance(agentic, dict):  # None, or the plan step's error
        return agentic
    return {
        "updated_management_plan_text": getattr(agentic, "updated_management_plan_text", None),
        "plan_issues": list(getattr(agentic, "plan_issues", []) or []),
    }


def checks_entry(result: Any, *, note: str, visit_date: str, model: Optional[str], app_version: str,
                 visit_id: str, saved_at: str) -> Entry:
    """The "checks_run" line for one run of the checks (result is artemis.visit.AnalysisResult)."""
    return {
        "event": "checks_run",
        "visit_id": visit_id,
        "patient_id": str(result.patient_id or ""),
        "visit_date": visit_date,
        "saved_at": saved_at,
        "note": note,
        "model": model,
        "app_version": app_version,
        "status": result.status,
        "ai_review": result.screening_outcome,
        "ai_review_ran": bool(result.screening_ran),
        "alerts": [{**asdict(a), "severity": (a.evidence or {}).get("severity")} for a in result.alerts],
        # In alert order, so each one lines up with its alert when the results are reopened.
        "results": [
            {
                "retrieved": [
                    {"chunk_id": c.chunk_id, "document": c.document, "metadata": c.metadata, "distance": c.distance}
                    for c in r.get("retrieved") or []
                ],
                "explanation": {"text": r["explanation"].text, "used_llm": r["explanation"].used_llm},
            }
            for r in result.results
        ],
        "screening_debug": result.screening_debug,
        "patient_summary": result.patient_summary,
        "agentic_enabled": bool(result.agentic_enabled),
        "plan": _plan(result.agentic_result),
    }


def finalized_entry(*, visit_id: Optional[str], patient_id: str, decisions: List[Dict[str, Any]], saved_at: str) -> Entry:
    """The "finalized" line: the clinician's decision on each alert (see artemis.review.decisions_from_state)."""
    return {"event": "finalized", "visit_id": visit_id, "patient_id": patient_id, "saved_at": saved_at, "decisions": decisions}


def append_entry(folder: Path, entry: Entry) -> Path:
    """Add one line to the patient's file. Earlier lines are never rewritten."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / _file_name(str(entry["patient_id"]))
    line = json.dumps(entry, ensure_ascii=False, default=str).encode("utf-8") + b"\n"
    with path.open("a+b") as fh:
        fh.seek(0, os.SEEK_END)
        if fh.tell() > 0:
            fh.seek(-1, os.SEEK_END)
            if fh.read(1) != b"\n":
                fh.write(b"\n")  # a half-written line from a crash stays on its own line
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    return path


def read_entries(folder: Path, patient_id: str) -> Tuple[List[Entry], int]:
    """The patient's events in the order written, and how many lines could not be read."""
    path = folder / _file_name(patient_id)
    if not path.exists():
        return [], 0
    entries: List[Entry] = []
    unreadable = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            unreadable += 1
            continue
        if not isinstance(entry, dict):
            unreadable += 1
        elif entry.get("patient_id") == patient_id:
            entries.append(entry)
    return entries, unreadable


def last_visit(entries: List[Entry]) -> Optional[Tuple[Entry, Optional[Entry]]]:
    """The last checks run, with its latest Finalize if there was one."""
    checks = next((e for e in reversed(entries) if e.get("event") == "checks_run"), None)
    if checks is None:
        return None
    finalized = next(
        (e for e in reversed(entries) if e.get("event") == "finalized" and e.get("visit_id") == checks.get("visit_id")),
        None,
    )
    return checks, finalized


def _saved_alert(a: Dict[str, Any]) -> Alert:
    missing = [k for k in ("alert_id", "title", "message") if not isinstance(a.get(k), str)]
    if missing:
        raise ValueError(f"saved alert has no {', '.join(missing)}")
    return Alert(
        alert_id=a["alert_id"], title=a["title"], message=a["message"], evidence=a.get("evidence") or {},
        query_hint=a.get("query_hint") or "", source=a.get("source") or "rule",
    )


def restore(checks: Entry, finalized: Optional[Entry] = None) -> Dict[str, Any]:
    """The screen's session values for a saved visit, as they were when it was saved.

    Raises ValueError (or TypeError) when the line's shape can't be rebuilt, for example a line
    written by an older version, rather than showing a half-empty visit.
    """
    alerts = [_saved_alert(a) for a in checks.get("alerts") or []]
    if len(checks.get("results") or []) != len(alerts):
        raise ValueError("saved results don't line up with the saved alerts")
    results = [
        {
            "alert": alert,
            "retrieved": [VectorSearchResult(**c) for c in r.get("retrieved") or []],
            "explanation": ExplanationResult(
                text=(r.get("explanation") or {}).get("text") or "",
                used_chunks=[],
                used_llm=bool((r.get("explanation") or {}).get("used_llm")),
            ),
        }
        for alert, r in zip(alerts, checks.get("results") or [])
    ]
    plan = checks.get("plan")
    if isinstance(plan, dict) and "updated_management_plan_text" in plan:
        plan = AgenticResult(
            updated_management_plan_text=plan.get("updated_management_plan_text"),
            plan_issues=list(plan.get("plan_issues") or []),
        )
    values: Dict[str, Any] = {
        "analysis_ran": True,
        "analysis_patient_id": checks.get("patient_id"),
        "analysis_note": checks.get("note") or "",
        "analysis_visit_id": checks.get("visit_id"),
        "analysis_saved_at": checks.get("saved_at"),
        "analysis_restored": True,
        "analysis_status": checks.get("status"),
        "analysis_screening_outcome": checks.get("ai_review") or "not_run",
        "analysis_alerts": alerts,
        "analysis_results": results,
        "analysis_use_ollama": bool(checks.get("ai_review_ran")),
        "analysis_screening_debug": checks.get("screening_debug"),
        "analysis_patient_summary": checks.get("patient_summary"),
        "agentic_debug_enabled": bool(checks.get("agentic_enabled")),
        "agentic_debug_result": plan,
        "finalized": finalized is not None,
        "analysis_finalized_at": (finalized or {}).get("saved_at"),
    }
    decided = {d.get("alert_id"): d for d in (finalized or {}).get("decisions") or []}
    for alert in alerts:
        d = decided.get(alert.alert_id) or {}
        values[f"alert_action_{alert.alert_id}"] = d.get("action") or "Unreviewed"
        values[f"alert_override_reason_{alert.alert_id}"] = d.get("reason") or ""
        values[f"alert_override_comment_{alert.alert_id}"] = d.get("comment") or ""
    return values
