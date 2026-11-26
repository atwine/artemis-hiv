"""Visit records in the database (plan item 4.5): what was checked, and what the clinician decided.

The same two events as the Phase 1 files (artemis/visit_record.py), as two tables:
- visit_check: one row per run of the checks, holding the "checks_run" entry's fields.
- alert_decision: one row per decision on one alert. Rows are only ever added; a changed mind
  is a new row, and the latest one for an alert counts (owner, 2026-11-26).

The tables' history is in backend/migrations (Alembic). `import_folder` copies the old files
in and can be run again safely: what is already there is skipped.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Session, SQLModel, select

from artemis.statuses import status_name

Json = JSON().with_variant(JSONB(), "postgresql")


def _utc(value: Any) -> datetime.datetime:
    """A saved time as an aware UTC datetime (SQLite hands them back without a zone)."""
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def iso(value: datetime.datetime) -> str:
    return _utc(value).isoformat(timespec="seconds")


class VisitCheck(SQLModel, table=True):
    __tablename__ = "visit_check"

    visit_id: str = Field(primary_key=True, max_length=64)
    patient_id: str = Field(index=True, max_length=200)
    visit_date: str = Field(max_length=10)
    saved_at: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    note: str = Field(sa_column=Column(Text, nullable=False))
    model: Optional[str] = Field(default=None, max_length=200)
    app_version: str = Field(max_length=64)
    status: str = Field(max_length=16)
    ai_review: str = Field(max_length=16)
    ai_review_ran: bool
    alerts: List[Dict[str, Any]] = Field(sa_column=Column(Json, nullable=False))
    results: List[Dict[str, Any]] = Field(sa_column=Column(Json, nullable=False))
    screening_debug: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(Json))
    patient_summary: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(Json))
    agentic_enabled: bool
    plan: Optional[Any] = Field(default=None, sa_column=Column(Json))
    # "api" (run through the backend) or "file import" (copied from Data/visit_records).
    origin: str = Field(max_length=16)


class AlertDecision(SQLModel, table=True):
    __tablename__ = "alert_decision"

    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: str = Field(foreign_key="visit_check.visit_id", index=True, max_length=64)
    alert_id: str = Field(max_length=200)
    source: str = Field(max_length=16)
    title: str = Field(sa_column=Column(Text, nullable=False))
    severity: Optional[str] = Field(default=None, max_length=16)
    action: str = Field(max_length=16)
    reason: str = Field(default="", max_length=64)
    comment: str = Field(default="", sa_column=Column(Text, nullable=False))
    saved_at: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


# The "checks_run" entry's fields that are stored as they are (saved_at and ai_review are handled apart).
_CHECK_FIELDS = [
    "visit_id", "patient_id", "visit_date", "note", "model", "app_version", "status", "ai_review_ran",
    "alerts", "results", "screening_debug", "patient_summary", "agentic_enabled", "plan",
]


def json_safe(value: Any) -> Any:
    """JSON-safe copy: dates and other objects become text, as in the files (json default=str)."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def check_from_entry(entry: Dict[str, Any], *, origin: str) -> VisitCheck:
    e = json_safe(entry)
    e["status"] = status_name(e.get("status"))  # an older file may say YELLOW (owner, 2026-11-26)
    return VisitCheck(
        **{k: e.get(k) for k in _CHECK_FIELDS},
        ai_review=e.get("ai_review") or "not_run",
        saved_at=_utc(e["saved_at"]),
        origin=origin,
    )


def entry_from_check(row: VisitCheck) -> Dict[str, Any]:
    """The row back as a "checks_run" entry, the shape artemis.visit_record.restore reads."""
    return {
        "event": "checks_run",
        **{k: getattr(row, k) for k in _CHECK_FIELDS},
        "saved_at": iso(row.saved_at),
        "ai_review": row.ai_review,
    }


def save_check(session: Session, entry: Dict[str, Any], *, origin: str) -> VisitCheck:
    row = check_from_entry(entry, origin=origin)
    session.add(row)
    session.commit()
    return row


def get_check(session: Session, visit_id: str) -> Optional[VisitCheck]:
    return session.get(VisitCheck, visit_id)


def _decision_rows(visit_id: str, decisions: List[Dict[str, Any]], saved_at: Any) -> List[AlertDecision]:
    when = _utc(saved_at)
    return [
        AlertDecision(
            visit_id=visit_id, alert_id=str(d["alert_id"]), source=str(d.get("source") or "rule"),
            title=str(d.get("title") or ""), severity=d.get("severity"), action=str(d["action"]),
            reason=str(d.get("reason") or ""), comment=str(d.get("comment") or ""), saved_at=when,
        )
        for d in decisions
    ]


def add_decisions(session: Session, visit_id: str, decisions: List[Dict[str, Any]], *, saved_at: Any) -> None:
    """Add the decisions in one step: all of them are saved, or none."""
    session.add_all(_decision_rows(visit_id, decisions, saved_at))
    session.commit()


def latest_decisions(session: Session, visit_id: str) -> Dict[str, AlertDecision]:
    """The latest decision on each alert of the visit."""
    rows = session.exec(
        select(AlertDecision).where(AlertDecision.visit_id == visit_id).order_by(AlertDecision.saved_at, AlertDecision.id)
    ).all()
    return {r.alert_id: r for r in rows}


def _same_decision(session: Session, row: AlertDecision) -> bool:
    return session.exec(
        select(AlertDecision.id).where(
            AlertDecision.visit_id == row.visit_id, AlertDecision.alert_id == row.alert_id,
            AlertDecision.saved_at == row.saved_at, AlertDecision.action == row.action,
            AlertDecision.reason == row.reason, AlertDecision.comment == row.comment,
        )
    ).first() is not None


def import_folder(session: Session, folder: Path) -> Dict[str, int]:
    """Copy the visit-record files (Data/visit_records/*.jsonl) into the database. The files are
    only read. Safe to rerun: a run or decision already in the database is counted, not added."""
    report = {"checks_added": 0, "decisions_added": 0, "already_there": 0, "unreadable_lines": 0, "skipped": 0}
    if not folder.is_dir():
        return report
    for path in sorted(folder.glob("*.jsonl")):
        entries, unreadable = _read_file(path)
        report["unreadable_lines"] += unreadable
        for e in [e for e in entries if e.get("event") == "checks_run"]:
            if not e.get("visit_id"):
                report["skipped"] += 1
            elif session.get(VisitCheck, str(e["visit_id"])) is not None:
                report["already_there"] += 1
            else:
                session.add(check_from_entry(e, origin="file import"))
                session.flush()
                report["checks_added"] += 1
        for e in [e for e in entries if e.get("event") == "finalized"]:
            visit_id = e.get("visit_id")
            if not visit_id or session.get(VisitCheck, str(visit_id)) is None:
                report["skipped"] += 1  # an older Finalize with no run id, or a run not in the files
                continue
            for row in _decision_rows(str(visit_id), list(e.get("decisions") or []), e["saved_at"]):
                if _same_decision(session, row):
                    report["already_there"] += 1
                else:
                    session.add(row)
                    session.flush()
                    report["decisions_added"] += 1
    session.commit()
    return report


def _read_file(path: Path):
    """Every readable entry in one file, whatever patient id it carries (the file is named from it)."""
    entries: List[Dict[str, Any]] = []
    unreadable = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            unreadable += 1
            continue
        if isinstance(entry, dict) and entry.get("patient_id"):
            entries.append(entry)
        else:
            unreadable += 1
    return entries, unreadable

