"""The backend's routes (plan item 4.2). Each one is a thin shell: check access, read the
request, call the existing code in artemis/, and shape the reply.

Run with `python -m backend`. Who may call what: ACCESS.md (enforced in backend/access.py).
"""

from __future__ import annotations

import copy
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from artemis import visit_record
from artemis.patient.store import UnreadableFile
from artemis.review import alert_resolution_ok, decisions_from_state
from artemis.rules.checks import Alert
from artemis.visit import AnalysisOptions, run_visit_analysis
from backend import records
from backend.access import AccessMiddleware, require, role_of, visible_patients
from backend.cards import cards_from_entry, plan_from_entry
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

Loaded = Tuple[PatientRecord, Dict[str, Any]]  # the checked record, and the record as stored


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
            out.append((record, item))
    return out


def _find(services: Services, patient_id: str) -> Loaded:
    found = next((p for p in load_patients(services) if p[0].patient_id == patient_id), None)
    if found is None:
        raise HTTPException(status_code=404, detail="No such patient.")
    return found


def _summary(record: PatientRecord) -> PatientSummary:
    return PatientSummary(
        patient_id=record.patient_id, name=record.name, sex=record.sex, age_years=record.age_years,
        art_regimen_current=record.art_regimen_current, visit_date=record.today_encounter.date,
    )


def _saved_alerts(row: records.VisitCheck) -> List[Alert]:
    return [
        Alert(alert_id=a["alert_id"], title=a.get("title") or "", message=a.get("message") or "",
              evidence=a.get("evidence") or {}, query_hint=a.get("query_hint") or "", source=a.get("source") or "rule")
        for a in row.alerts
    ]


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
        loaded = visible_patients(role_of(request), load_patients(services))
        return [_summary(record) for record, _ in loaded]

    @app.get("/api/patients/{patient_id}", response_model=PatientDetail, dependencies=[Depends(require("patients", "view"))])
    def get_patient(patient_id: str) -> Dict[str, Any]:
        record, _ = _find(services, patient_id)
        return record.model_dump()

    @app.post(
        "/api/patients/{patient_id}/visits",
        response_model=VisitCheckResponse,
        dependencies=[Depends(require("patients", "view")), Depends(require("visit_records", "create"))],
    )
    def run_visit_check(patient_id: str, body: VisitCheckRequest) -> VisitCheckResponse:
        _, patient = _find(services, patient_id)
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
        entry = records.plain(visit_record.checks_entry(
            result,
            note=body.note,
            visit_date=str((patient.get("today_encounter") or {}).get("date") or ""),
            model=getattr(client, "model", None) if client is not None else None,
            app_version=services.app_version,
            visit_id=visit_id,
            saved_at=saved_at,
        ))
        saved = False
        if services.engine is not None:
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
            raise HTTPException(status_code=503, detail="The visit-record database is not set up.")
        with Session(services.engine) as session:
            row = records.get_check(session, visit_id)
            if row is None:
                raise HTTPException(status_code=404, detail="No such visit.")
            alerts = {a.alert_id: a for a in _saved_alerts(row)}
            state: Dict[str, Any] = {}
            for d in body.decisions:
                if d.alert_id not in alerts:
                    raise HTTPException(status_code=422, detail="An alert in the request isn't in this visit.")
                state[f"alert_action_{d.alert_id}"] = d.action
                state[f"alert_override_reason_{d.alert_id}"] = d.reason or ""
                state[f"alert_override_comment_{d.alert_id}"] = d.comment
                # Today's Finalize rule: an override needs a reason, and "Other" needs a comment.
                if not alert_resolution_ok(state, d.alert_id):
                    raise HTTPException(status_code=422, detail="An override needs a reason, and 'Other' needs a comment.")
            chosen = [alerts[a] for a in dict.fromkeys(d.alert_id for d in body.decisions)]
            records.add_decisions(session, visit_id, decisions_from_state(state, chosen), saved_at=visit_record.now_utc())
            latest = records.latest_decisions(session, visit_id)
            order = [a["alert_id"] for a in row.alerts]
        return DecisionsResponse(
            visit_id=visit_id,
            decisions=[
                DecisionOut(alert_id=a, action=latest[a].action, reason=latest[a].reason, comment=latest[a].comment, saved_at=records.iso(latest[a].saved_at))
                for a in order if a in latest
            ],
            all_resolved=all(a in latest for a in order),
            unresolved=[a for a in order if a not in latest],
        )

    return app


app = create_app()
