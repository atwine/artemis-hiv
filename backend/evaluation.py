"""The evaluation through the backend itself (plan 4C.5, owner 2026-11-27: "A, through the backend").

One run of a case: the case's patient goes into a throwaway database the way the app stores
patients (backend/patients_db.py), then the run presses "run checks" and "Compare plans" through
the backend's own routes, as the website does, and the record is read back from what the backend
saved. So the scores measure the app's own path, and the evaluation can't drift from it.

The database is in memory and thrown away after the run; nothing touches the app's database.
The record keeps the fields Phase 2 saved, except the model's raw error text, which the backend
never saves (the short outcome, `screening_outcome`, stays).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from artemis.evaluation.cases import Case
from artemis.evaluation.runner import MeteredClient, cost_of, effective_temperature
from backend import patients_db, records
from backend.services import Services, database_patients
from backend.settings import Settings

# The app's own page, so the access check lets the run in (ACCESS.md: this laptop only).
_FROM_THE_APP = {"Origin": "http://localhost:3000"}
_SEARCH_DOWN = "The guideline search is unavailable, so no plan was made."


class RunFailed(RuntimeError):
    """The backend refused a request, so there is no record to save. `cost_usd` is what the run
    had already spent on the model, which no saved record counts."""

    def __init__(self, message: str, cost_usd: float = 0.0) -> None:
        super().__init__(message)
        self.cost_usd = cost_usd


def memory_engine() -> Engine:
    """A throwaway database in memory with the app's tables, checking the links between tables as
    Postgres does (SQLite skips them unless told)."""
    import backend.clinic_db  # noqa: F401  (registers the tables)

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    SQLModel.metadata.create_all(engine)
    return engine


def _backend(engine: Engine, rag: Any, client: Any):
    from fastapi.testclient import TestClient

    from backend.main import create_app

    services = Services(patients=database_patients(engine), search=lambda: rag, model_client=lambda: client,
                        engine=engine, app_version="evaluation")
    # No limit worth reaching: a run is many checks in a row, and the spend is guarded by its cap.
    app = create_app(settings=Settings(visit_checks_per_minute=1_000_000), services=services)
    return TestClient(app, base_url="http://localhost")


def _post(http: Any, path: str, **kw: Any) -> Any:
    r = http.post(path, headers=_FROM_THE_APP, **kw)
    if r.status_code != 200 and not (r.status_code == 503 and r.json().get("detail") == _SEARCH_DOWN):
        raise RunFailed(f"{path}: HTTP {r.status_code} {r.text[:200]}")
    return r


def as_the_app_reads(patients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The patients as the app reads them: saved into a throwaway database and read back
    (backend/patients_db.py), so a measurement sees each record in the app's own shape."""
    engine = memory_engine()
    try:
        with Session(engine) as session:
            patients_db.import_records(session, patients, origin="seed")
        with Session(engine) as session:
            return patients_db.load_all(session)
    finally:
        engine.dispose()


def run_visit(patient: Dict[str, Any], note: str, client: Any, rag: Any) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """One visit through the backend: the patient into a throwaway database (refused there, before
    anything runs, if the database can't hold it), "run checks", then "Compare plans". Returns the
    saved check as its "checks_run" entry, and the saved plan's text and issues (None when no plan
    was made: the guideline search was down)."""
    engine = memory_engine()
    try:
        with Session(engine) as session:
            patients_db.import_records(session, [patient], origin="seed")
        with _backend(engine, rag, client) as http:
            visit = _post(http, f"/api/patients/{patient['patient_id']}/visits", json={"note": note}).json()
            _post(http, f"/api/visits/{visit['visit_id']}/plan")
        with Session(engine) as session:
            entry = records.entry_from_check(records.get_check(session, visit["visit_id"]))
            plan = records.latest_plan(session, visit["visit_id"])
            made = {"plan_text": plan.plan_text, "issues": list(plan.issues)} if plan else None
    finally:
        engine.dispose()
    return entry, made


def run_case(case: Case, client: Any, rag: Any, *, label: str, repeat: int, price_in: float = 0.0,
             price_out: float = 0.0, temperature: Optional[float] = None) -> Dict[str, Any]:
    """One visit of the case through the backend (the check, then its plan), as a JSON-ready record."""
    metered = MeteredClient(client)
    note = (case.patient.get("today_encounter") or {}).get("note") or ""
    t0 = time.perf_counter()
    try:
        check, plan = run_visit(case.patient, note, metered, rag)
    except RunFailed as exc:
        raise RunFailed(str(exc), cost_of(metered.usages, price_in, price_out)) from exc
    seconds = time.perf_counter() - t0
    alerts = [{k: v for k, v in a.items() if k != "severity"} for a in check["alerts"]]  # severity: the API's copy
    return {
        "case_id": case.case_id,
        "model": label,
        "model_id": getattr(client, "model", None),
        "repeat": repeat,
        "temperature": effective_temperature(temperature),
        "seconds": round(seconds, 1),
        "calls": metered.usages,
        "cost_usd": cost_of(metered.usages, price_in, price_out),
        "status": check["status"],
        "screening_outcome": check["ai_review"],
        "alerts": alerts,
        "retrieved": {a["alert_id"]: [c["chunk_id"] for c in r.get("retrieved") or []]
                      for a, r in zip(alerts, check["results"])},
        "screening": check["screening_debug"],
        "plan_text": plan["plan_text"] if plan else None,
        "plan_issues": plan["issues"] if plan else [],
    }
