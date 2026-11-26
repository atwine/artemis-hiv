"""The backend's routes (plan item 4.2). Each one is a thin shell: check access, read the
request, call the existing code in artemis/ (and the plain functions in backend/), and shape
the reply.

Run with `python -m backend` (it builds the app with `create_app` when the server starts).
Who may call what: ACCESS.md (enforced in backend/access.py).
"""

from __future__ import annotations

import copy
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from artemis import visit_record
from artemis.patient.labs import read_lab_entries, read_lab_notes
from artemis.patient.store import UnreadableFile
from artemis.visit import AnalysisOptions, run_visit_analysis
from backend import records
from backend.access import AccessMiddleware, require, role_of, visible_patients
from artemis.screen_text import DISCLAIMER, FINALIZE_BLOCKED
from backend.cards import banners_for, cards_from_entry, plan_from_entry
from backend.decisions import BadDecision, decision_rows, ready_to_finalize, summary
from backend.models import (
    Appointment,
    ClinicDay,
    ClinicDaySchedule,
    DayCounts,
    DecisionOut,
    DecisionsRequest,
    DecisionsResponse,
    FinalizeRequest,
    FinalizeResponse,
    LabNote,
    LabResult,
    PatientDetail,
    PatientRecord,
    PatientSummary,
    SavedVisit,
    VisitCheckRequest,
    VisitCheckResponse,
    VisitSummary,
)
from backend.services import Services, default_services
from backend.settings import Settings, settings_from_env

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Loaded:
    record: PatientRecord  # checked once, when loaded
    stored: Dict[str, Any]  # the record exactly as in the file, which the visit check reads


def load_patients(services: Services) -> List[Loaded]:
    """Every patient, checked once here. A file or record that can't be read is reported (500),
    never skipped: skipping hid saved cases before (fix 10, G16)."""
    try:
        raw = services.patients()
    except (UnreadableFile, OSError) as exc:
        logger.warning("Patient list not read: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="The patient list could not be read.")
    out: List[Loaded] = []
    seen = set()
    for position, item in enumerate(raw):
        try:
            record = PatientRecord.model_validate(item)
        except ValidationError as exc:
            logger.warning("Patient record %d is invalid (%d problems)", position, exc.error_count())
            raise HTTPException(status_code=500, detail="The patient list could not be read.")
        if record.patient_id not in seen:  # the first record with an id wins, as on the screen
            seen.add(record.patient_id)
            out.append(Loaded(record=record, stored=item))
    return out


def _find(services: Services, patient_id: str) -> Loaded:
    found = next((p for p in load_patients(services) if p.record.patient_id == patient_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="No such patient.")
    return found


def _summary(record: PatientRecord) -> PatientSummary:
    return PatientSummary(
        patient_id=record.patient_id, name=record.name, sex=record.sex, age_years=record.age_years,
        art_regimen_current=record.art_regimen_current, visit_date=record.today_encounter.date,
    )


def _detail(p: Loaded) -> PatientDetail:
    """A patient for the screen, each lab result with its value, unit and date apart."""
    labs: Dict[str, List[LabResult]] = {}
    for e in read_lab_entries(p.stored):
        labs.setdefault(e.test, []).append(LabResult(date=e.date.isoformat(), value=e.value, unit=e.unit, source=e.source))
    notes = [LabNote(date=n.date.isoformat() if n.date else None, source=n.source, text=n.text) for n in read_lab_notes(p.stored)]
    return PatientDetail(**{**p.record.model_dump(), "labs": labs, "lab_notes": notes})


def _visit_reply(entry: Dict[str, Any], *, record_saved: bool) -> Dict[str, Any]:
    """A saved "checks_run" entry as the screen gets it: the same for a fresh check and a reopened one."""
    cards = cards_from_entry(entry)
    return dict(
        visit_id=entry["visit_id"], patient_id=str(entry["patient_id"]), visit_date=entry["visit_date"],
        saved_at=entry["saved_at"], status=entry["status"], ai_review=entry["ai_review"], model=entry["model"],
        cards=cards, plan=plan_from_entry(entry), record_saved=record_saved,
        banners=banners_for(entry), disclaimer=DISCLAIMER, finalize_note=FINALIZE_BLOCKED if cards else None,
    )


def _latest(session: Session, visit_id: str) -> Dict[str, DecisionOut]:
    """The latest saved decision on each alert of the visit, as the API sends it."""
    return {
        a: DecisionOut(alert_id=a, action=d.action, reason=d.reason, comment=d.comment, saved_at=records.iso(d.saved_at))
        for a, d in records.latest_decisions(session, visit_id).items()
    }


def board_row(booking: Any, record: PatientRecord, latest: Optional[records.VisitCheck], reviewed: int,
              finalized: Optional[str]) -> Appointment:
    """One row of the day board, from the booking, the patient and their latest saved check."""
    state = "waiting" if latest is None else ("done" if finalized else "needs_you")
    return Appointment(
        time=booking.time, patient_id=record.patient_id, name=record.name or booking.name or record.patient_id,
        age_years=record.age_years, sex=record.sex, regimen="/".join(record.art_regimen_current), state=state,
        visit_id=latest.visit_id if latest else None, status=latest.status if latest else None,
        ai_review=latest.ai_review if latest else None, alert_count=len(latest.alerts) if latest else 0,
        reviewed_count=reviewed, finalized_at=finalized,
    )


def day_counts(rows: List[Appointment]) -> DayCounts:
    return DayCounts(
        booked=len(rows),
        checked=sum(r.state != "waiting" for r in rows),
        finalized=sum(r.state == "done" for r in rows),
        left_in_red=sum(r.status == "RED" and r.state != "done" for r in rows),
    )


def _no_database() -> HTTPException:
    return HTTPException(status_code=503, detail="The visit-record database is not set up.")


def create_app(*, settings: Optional[Settings] = None, services: Optional[Services] = None) -> FastAPI:
    settings = settings or settings_from_env()
    services = services or default_services(settings)
    app = FastAPI(title="ARTEMIS-HIV backend", version="0.1.0")
    app.state.services = services
    # Last added runs first: the access check refuses before CORS, routing or body parsing.
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"], allow_credentials=False,
    )
    app.add_middleware(AccessMiddleware, settings=settings)

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/patients", response_model=List[PatientSummary], dependencies=[Depends(require("patients", "view"))])
    def list_patients(request: Request) -> List[PatientSummary]:
        return [_summary(p.record) for p in visible_patients(role_of(request), load_patients(services))]

    @app.get("/api/patients/{patient_id}", response_model=PatientDetail, dependencies=[Depends(require("patients", "view"))])
    def get_patient(patient_id: str) -> PatientDetail:
        return _detail(_find(services, patient_id))

    @app.post(
        "/api/patients/{patient_id}/visits",
        response_model=VisitCheckResponse,
        dependencies=[
            Depends(require("patients", "view")),
            Depends(require("visit_records", "create")),
            Depends(require("guidelines", "view")),  # the cards quote guideline passages
        ],
    )
    def run_visit_check(patient_id: str, body: VisitCheckRequest) -> VisitCheckResponse:
        patient = _find(services, patient_id).stored
        if services.engine is None:
            raise _no_database()  # nothing could be saved or decided on, so nothing is run or paid for
        client = services.model_client() if body.use_ai else None
        if body.use_ai and client is None:
            raise HTTPException(status_code=503, detail="No AI model server is set up.")
        result = run_visit_analysis(
            patient=copy.deepcopy(patient),
            today_note=body.note,
            rag=services.search(),
            llm_client=client,
            options=AnalysisOptions(top_k=services.top_k, use_llm=body.use_ai, agentic=body.include_plan),
        )
        if isinstance(result.agentic_result, dict) and "error" in result.agentic_result:
            logger.warning("Plan step failed: %s", result.agentic_result.get("type"))
        visit_id, saved_at = uuid.uuid4().hex, records.now()
        entry = records.json_safe(visit_record.checks_entry(
            result,
            note=body.note,
            visit_date=str((patient.get("today_encounter") or {}).get("date") or ""),
            model=getattr(client, "model", None) if client is not None else None,
            app_version=services.app_version,
            visit_id=visit_id,
            saved_at=saved_at,
        ))
        saved = False
        try:
            with Session(services.engine) as session:
                records.save_check(session, entry, origin="api")
            saved = True
        except SQLAlchemyError as exc:
            # The results are still shown, as on the Streamlit screen (fix 9).
            logger.warning("Visit record not saved: %s", type(exc).__name__)
        return VisitCheckResponse(**_visit_reply(entry, record_saved=saved))

    @app.post(
        "/api/visits/{visit_id}/decisions",
        response_model=DecisionsResponse,
        dependencies=[Depends(require("visit_records", "create"))],
    )
    def record_decisions(visit_id: str, body: DecisionsRequest) -> DecisionsResponse:
        if services.engine is None:
            raise _no_database()
        with Session(services.engine) as session:
            row = records.get_check(session, visit_id)
            if row is None:
                raise HTTPException(status_code=404, detail="No such visit.")
            # Read back through the same check the Streamlit app uses to reopen a saved visit.
            alerts = visit_record.restore(records.entry_from_check(row))["analysis_alerts"]
            try:
                rows = decision_rows(alerts, body.decisions)
            except BadDecision as exc:
                raise HTTPException(status_code=422, detail=str(exc))
            records.add_decisions(session, visit_id, rows, saved_at=visit_record.now_utc())
            latest = _latest(session, visit_id)
            finalized = records.finalized_at(session, visit_id)  # None: a new decision reopens a visit
        decided, unresolved = summary([a.alert_id for a in alerts], latest)
        return DecisionsResponse(
            visit_id=visit_id, decisions=decided, all_resolved=not unresolved, unresolved=unresolved,
            finalize_note=FINALIZE_BLOCKED if unresolved else None, finalized_at=finalized,
        )

    @app.post(
        "/api/visits/{visit_id}/finalize",
        response_model=FinalizeResponse,
        dependencies=[Depends(require("visit_records", "create"))],
    )
    def finalize_visit(visit_id: str, body: Optional[FinalizeRequest] = None) -> FinalizeResponse:
        """Close a visit once every alert is decided. Again with nothing changed: the same reply,
        nothing new saved. After a later decision reopened it: a new Finalize (owner, 2026-11-26)."""
        if services.engine is None:
            raise _no_database()
        with Session(services.engine) as session:
            row = records.get_check(session, visit_id)
            if row is None:
                raise HTTPException(status_code=404, detail="No such visit.")
            alerts = visit_record.restore(records.entry_from_check(row))["analysis_alerts"]
            current = records.current_finalize(session, visit_id)
            if current is None:
                latest = _latest(session, visit_id)
                if not ready_to_finalize(alerts, latest):
                    raise HTTPException(status_code=422, detail=FINALIZE_BLOCKED)
                decided, _ = summary([a.alert_id for a in alerts], latest)
                current = records.add_finalize(
                    session, visit_id, [d.model_dump() for d in decided], finalized_at=visit_record.now_utc()
                )
            return FinalizeResponse(
                visit_id=visit_id, finalized_at=records.iso(current.finalized_at),
                decisions=[DecisionOut(**d) for d in current.decisions],
            )

    @app.get("/api/visits/{visit_id}", response_model=SavedVisit, dependencies=[
        Depends(require("visit_records", "view")), Depends(require("guidelines", "view")),
    ])
    def reopen_visit(visit_id: str) -> SavedVisit:
        """A saved visit as it was shown, with its decisions and Finalize. No new AI call."""
        if services.engine is None:
            raise _no_database()
        with Session(services.engine) as session:
            row = records.get_check(session, visit_id)
            if row is None:
                raise HTTPException(status_code=404, detail="No such visit.")
            entry = records.entry_from_check(row)
            latest = _latest(session, visit_id)
            finalized = records.finalized_at(session, visit_id)
        reply = _visit_reply(entry, record_saved=True)
        decided, unresolved = summary([c.extension.alert_id for c in reply["cards"]], latest)
        reply["finalize_note"] = FINALIZE_BLOCKED if unresolved and finalized is None else None
        return SavedVisit(
            **reply, note=entry["note"], decisions=decided, all_resolved=not unresolved,
            unresolved=unresolved, finalized_at=finalized,
        )

    @app.get("/api/patients/{patient_id}/visits", response_model=List[VisitSummary], dependencies=[
        Depends(require("patients", "view")), Depends(require("visit_records", "view")),
    ])
    def past_checks(patient_id: str) -> List[VisitSummary]:
        """A patient's saved checks, newest first."""
        _find(services, patient_id)
        if services.engine is None:
            raise _no_database()
        with Session(services.engine) as session:
            return [
                VisitSummary(
                    visit_id=row.visit_id, visit_date=row.visit_date, saved_at=records.iso(row.saved_at),
                    status=row.status, ai_review=row.ai_review, model=row.model, alert_count=len(row.alerts),
                    decided_count=len(records.latest_decisions(session, row.visit_id)),
                    finalized_at=records.finalized_at(session, row.visit_id),
                )
                for row in records.checks_for(session, patient_id)
            ]

    @app.get("/api/clinic-day", response_model=ClinicDay, dependencies=[
        Depends(require("clinic_day", "view")), Depends(require("patients", "view")),
        Depends(require("visit_records", "view")),
    ])
    def clinic_day() -> ClinicDay:
        """The demo day's board: each booking with the state of the patient's latest saved check,
        whenever it ran (owner, 2026-11-26)."""
        patients = {p.record.patient_id: p.record for p in load_patients(services)}
        try:
            schedule = ClinicDaySchedule.model_validate(services.clinic_day())
            missing = [b.patient_id for b in schedule.appointments if b.patient_id not in patients]
            if missing:
                raise ValueError(f"{len(missing)} booking(s) for patients with no record")
        except (OSError, ValueError) as exc:  # pydantic's ValidationError is a ValueError
            logger.warning("Clinic day not read: %s", type(exc).__name__)
            raise HTTPException(status_code=500, detail="The clinic day could not be read.")
        if services.engine is None:  # nothing can have been checked
            rows = [board_row(b, patients[b.patient_id], None, 0, None) for b in schedule.appointments]
        else:
            rows = []
            with Session(services.engine) as session:
                for b in schedule.appointments:
                    latest = next(iter(records.checks_for(session, b.patient_id)), None)
                    reviewed = len(records.latest_decisions(session, latest.visit_id)) if latest else 0
                    finalized = records.finalized_at(session, latest.visit_id) if latest else None
                    rows.append(board_row(b, patients[b.patient_id], latest, reviewed, finalized))
        return ClinicDay(
            clinic=schedule.clinic, room=schedule.room, clinician=schedule.clinician,
            date=schedule.date.isoformat(), appointments=rows, counts=day_counts(rows),
        )

    return app
