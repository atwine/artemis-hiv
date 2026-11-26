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
from artemis.patient.store import UnreadableFile
from artemis.visit import AnalysisOptions, run_visit_analysis
from backend import records
from backend.access import AccessMiddleware, require, role_of, visible_patients
from backend.cards import cards_from_entry, plan_from_entry
from backend.decisions import BadDecision, decision_rows, summary
from backend.models import (
    DecisionOut,
    DecisionsRequest,
    DecisionsResponse,
    PatientDetail,
    PatientRecord,
    PatientSummary,
    VisitCheckRequest,
    VisitCheckResponse,
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
    def get_patient(patient_id: str) -> Dict[str, Any]:
        return _find(services, patient_id).record.model_dump()

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
        visit_id, saved_at = uuid.uuid4().hex, visit_record.now_utc()
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
        return VisitCheckResponse(
            visit_id=visit_id, patient_id=str(entry["patient_id"]), visit_date=entry["visit_date"],
            saved_at=saved_at, status=entry["status"], ai_review=entry["ai_review"], model=entry["model"],
            cards=cards_from_entry(entry), plan=plan_from_entry(entry), record_saved=saved,
        )

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
            latest = {
                a: DecisionOut(alert_id=a, action=d.action, reason=d.reason, comment=d.comment, saved_at=records.iso(d.saved_at))
                for a, d in records.latest_decisions(session, visit_id).items()
            }
        decided, unresolved = summary([a.alert_id for a in alerts], latest)
        return DecisionsResponse(visit_id=visit_id, decisions=decided, all_resolved=not unresolved, unresolved=unresolved)

    return app
