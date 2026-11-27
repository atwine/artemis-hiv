"""Visit records in the database (plan item 4.5): what was checked, and what the clinician decided.

- visit_check: one row per run of the checks, holding the "checks_run" entry's fields
  (checks_entry builds the entry; saved_alerts reads its alerts back).
- alert_decision: one row per decision on one alert. Rows are only ever added; a changed mind
  is a new row, and the latest one for an alert counts (owner, 2026-11-26).
- visit_finalize: each Finalize; visit_plan: each plan "Compare plans" made.

The tables' history is in backend/migrations (Alembic).
"""

from __future__ import annotations

import datetime
import json
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, Column, DateTime, Text, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Session, SQLModel, select

from artemis.guidelines.vector_store import VectorSearchResult
from artemis.rules.checks import Alert
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
    """ISO text in UTC: whole seconds, or microseconds when the time has them."""
    return _utc(value).isoformat(timespec="auto")


def now() -> str:
    """This moment, to the microsecond, so two checks saved in one second still sort in order."""
    return iso(datetime.datetime.now(datetime.timezone.utc))


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
    # "api" (run through the backend); older rows may say "file import" (copied from the Phase 1 files).
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


class VisitFinalize(SQLModel, table=True):
    """One Finalize of a visit. Never changed: a decision added afterwards reopens the visit
    until it is finalized again (owner, 2026-11-26), and every Finalize stays in the record."""

    __tablename__ = "visit_finalize"
    # One Finalize per set of decisions: two Finalize calls racing can't both save.
    __table_args__ = (UniqueConstraint("visit_id", "last_decision_id", name="uq_visit_finalize_covers"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: str = Field(foreign_key="visit_check.visit_id", index=True, max_length=64)
    finalized_at: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    # The newest decision row this Finalize covers (0 for a visit with no decisions). A decision
    # row with a higher id was added afterwards, so the visit is open again.
    last_decision_id: int = 0
    # The decision on each alert as finalized, in alert order, as the files' "finalized" line has.
    decisions: List[Dict[str, Any]] = Field(sa_column=Column(Json, nullable=False))


class VisitPlan(SQLModel, table=True):
    """One AI management plan made for a saved visit by "Compare plans" (owner, 2026-11-27). Rows
    are only ever added; the latest one for a visit is the one shown."""

    __tablename__ = "visit_plan"

    id: Optional[int] = Field(default=None, primary_key=True)
    visit_id: str = Field(foreign_key="visit_check.visit_id", index=True, max_length=64)
    made_at: datetime.datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    model: Optional[str] = Field(default=None, max_length=200)
    outcome: str = Field(max_length=16)  # "made" (a readable plan) or "failed"
    plan_text: Optional[str] = Field(default=None, sa_column=Column(Text))  # the AI's plan as it came back
    issues: List[str] = Field(sa_column=Column(Json, nullable=False))  # the checks it failed, as short codes
    error_type: Optional[str] = Field(default=None, max_length=200)  # the failure's kind only, never its text


def save_plan(session: Session, row: VisitPlan) -> VisitPlan:
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def latest_plan(session: Session, visit_id: str) -> Optional[VisitPlan]:
    """The plan shown for a visit: the latest one made."""
    return session.exec(
        select(VisitPlan).where(VisitPlan.visit_id == visit_id).order_by(VisitPlan.made_at.desc(), VisitPlan.id.desc())
    ).first()


# The "checks_run" entry's fields that are stored as they are (saved_at and ai_review are handled apart).
_CHECK_FIELDS = [
    "visit_id", "patient_id", "visit_date", "note", "model", "app_version", "status", "ai_review_ran",
    "alerts", "results", "screening_debug", "patient_summary", "agentic_enabled", "plan",
]


def json_safe(value: Any) -> Any:
    """JSON-safe copy: dates and other objects become text, as in the files (json default=str)."""
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def checks_entry(result: Any, *, note: str, visit_date: str, model: Optional[str], app_version: str,
                 visit_id: str, saved_at: str) -> Dict[str, Any]:
    """The "checks_run" entry for one visit check (result is artemis.visit.AnalysisResult): what
    is saved, and what the reply is built from, so a fresh check and a reopened one read the same.
    It holds no plan: only "Compare plans" makes one (owner, 2026-11-27); the two plan fields stay
    for the records saved before."""
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
        # In alert order, so each one lines up with its alert when the visit is reopened.
        "results": [
            {
                "retrieved": [
                    {"chunk_id": c.chunk_id, "document": c.document, "metadata": c.metadata, "distance": c.distance}
                    for c in r.get("retrieved") or []
                ],
                "explanation": {"text": r["explanation"].text},
            }
            for r in result.results
        ],
        "screening_debug": result.screening_debug,
        "patient_summary": result.patient_summary,
        "agentic_enabled": False,
        "plan": None,
    }


@dataclass(frozen=True)
class SavedAlert:
    """One alert of a saved visit check, with the passages and explanation it was shown with."""

    alert: Alert
    retrieved: List[VectorSearchResult]
    explanation: str
    severity: Optional[str]


def _saved_alert(a: Dict[str, Any]) -> Alert:
    missing = [k for k in ("alert_id", "title", "message") if not isinstance(a.get(k), str)]
    if missing:
        raise ValueError(f"saved alert has no {', '.join(missing)}")
    return Alert(
        alert_id=a["alert_id"], title=a["title"], message=a["message"], evidence=a.get("evidence") or {},
        query_hint=a.get("query_hint") or "", source=a.get("source") or "rule",
    )


def saved_alerts(entry: Dict[str, Any]) -> List[SavedAlert]:
    """A saved check's alerts, rebuilt. Results that don't line up with the alerts, or an alert
    that can't be rebuilt, raise ValueError rather than show some alerts and lose others."""
    alerts = entry.get("alerts") or []
    results = entry.get("results") or []
    if len(results) != len(alerts):
        raise ValueError("saved results don't line up with the saved alerts")
    return [
        SavedAlert(
            alert=_saved_alert(a),
            retrieved=[VectorSearchResult(**c) for c in r.get("retrieved") or []],
            explanation=(r.get("explanation") or {}).get("text") or "",
            severity=a.get("severity"),
        )
        for a, r in zip(alerts, results)
    ]


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
    """The row back as a "checks_run" entry, the shape checks_entry writes."""
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


def checks_for(session: Session, patient_id: str) -> List[VisitCheck]:
    """A patient's saved visit checks, newest first."""
    return list(session.exec(
        select(VisitCheck).where(VisitCheck.patient_id == patient_id).order_by(VisitCheck.saved_at.desc(), VisitCheck.visit_id)
    ).all())


def _last_decision_id(session: Session, visit_id: str) -> Optional[int]:
    return session.exec(
        select(AlertDecision.id).where(AlertDecision.visit_id == visit_id).order_by(AlertDecision.id.desc())
    ).first()


def current_finalize(session: Session, visit_id: str) -> Optional[VisitFinalize]:
    """The Finalize that still holds: the latest one, unless a decision was added after it."""
    latest = session.exec(
        select(VisitFinalize).where(VisitFinalize.visit_id == visit_id).order_by(VisitFinalize.id.desc())
    ).first()
    if latest is None:
        return None
    newest = _last_decision_id(session, visit_id)
    return latest if newest is None or latest.last_decision_id >= newest else None


def finalized_at(session: Session, visit_id: str) -> Optional[str]:
    """When the visit was finalized, or None while it is open."""
    f = current_finalize(session, visit_id)
    return iso(f.finalized_at) if f is not None else None


def add_finalize(session: Session, visit_id: str, decisions: List[Dict[str, Any]], *, finalized_at: Any) -> VisitFinalize:
    """Record a Finalize covering every decision saved so far. If one covering the same decisions
    was saved meanwhile (two calls racing), that one is returned and nothing new is saved."""
    covers = _last_decision_id(session, visit_id) or 0
    row = VisitFinalize(visit_id=visit_id, finalized_at=_utc(finalized_at), last_decision_id=covers, decisions=json_safe(decisions))
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return session.exec(
            select(VisitFinalize).where(VisitFinalize.visit_id == visit_id, VisitFinalize.last_decision_id == covers)
        ).one()
    return row
