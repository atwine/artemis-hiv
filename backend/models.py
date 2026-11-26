"""The shapes the backend reads and returns (plan item 4.1).

Requests forbid unknown fields, so a field the screen doesn't show is refused rather than
quietly used (ACCESS.md section 5). Alerts go out as CDS Hooks cards
(https://cds-hooks.hl7.org/2.0/#cds-service-response): summary, detail, indicator, source,
suggestions and overrideReasons, with ARTEMIS's own fields under `extension`.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.review import OVERRIDE_REASONS

# Built from the one list the Streamlit screen uses too, so the two can't drift apart.
OverrideReason = Literal[tuple(OVERRIDE_REASONS)]  # type: ignore[valid-type]

Status = Literal["GREEN", "YELLOW", "RED", "INCOMPLETE"]
# What happened to the AI review (artemis.visit.AnalysisResult.screening_outcome).
AiReview = Literal["not_run", "ok", "failed", "unreadable", "cut_off", "partly_read"]
AlertKind = Literal["rule", "ai"]
Action = Literal["Acknowledge", "Override"]

# --- Patients ---------------------------------------------------------------------------


class TodayEncounter(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str
    note: str = ""
    orders: List[Any] = []
    med_changes: List[Any] = []

    @field_validator("date")
    @classmethod
    def _iso_date(cls, v: str) -> str:
        datetime.date.fromisoformat(v)  # the rules read it as YYYY-MM-DD
        return v


class PatientRecord(BaseModel):
    """A patient as stored in Data/*.json, checked once when it's loaded. Unknown fields are kept,
    so the visit check sees the record exactly as written."""

    model_config = ConfigDict(extra="allow")

    patient_id: str = Field(min_length=1, max_length=200)
    name: str = ""
    sex: str = ""
    age_years: Optional[int] = None
    art_regimen_current: List[str] = []
    other_medications: List[str] = []
    regimen_history: List[Dict[str, Any]] = []
    intake: Dict[str, Any] = {}
    visits: List[Dict[str, Any]] = []
    labs: Dict[str, List[Dict[str, Any]]] = {}
    today_encounter: TodayEncounter


class PatientSummary(BaseModel):
    """One row of the patient list."""

    patient_id: str
    name: str
    sex: str
    age_years: Optional[int]
    art_regimen_current: List[str]
    visit_date: str


class PatientDetail(BaseModel):
    """A patient's record for the screen. Only these fields go out: the demo answer key
    (expected_demo_outcome) and anything else in the file stay behind."""

    patient_id: str
    name: str
    sex: str
    age_years: Optional[int]
    art_regimen_current: List[str]
    other_medications: List[str]
    regimen_history: List[Dict[str, Any]]
    intake: Dict[str, Any]
    visits: List[Dict[str, Any]]
    labs: Dict[str, List[Dict[str, Any]]]
    today_encounter: Dict[str, Any]


# --- Cards (CDS Hooks) ------------------------------------------------------------------


class _CdsOut(BaseModel):
    """CDS Hooks fields go out in the spec's camelCase (overrideReasons, isRecommended)."""

    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class Coding(_CdsOut):
    code: str
    system: str
    display: str


class Source(_CdsOut):
    label: str
    topic: Optional[Coding] = None


class Suggestion(_CdsOut):
    label: str
    uuid: str
    is_recommended: bool = Field(default=True, alias="isRecommended")
    # FHIR create/update/delete actions; ARTEMIS suggests in words only, so always empty.
    actions: List[Dict[str, Any]] = []


class Passage(_CdsOut):
    """A guideline passage an alert rests on (plan done-criterion 4)."""

    chunk_id: str
    text: str
    source_path: Optional[str] = None
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = {}


class CardExtension(_CdsOut):
    alert_id: str  # the alert's own id, which decisions refer to
    kind: AlertKind
    severity: Optional[str] = None
    explanation: str = ""
    passages: List[Passage] = []


class Card(_CdsOut):
    uuid: str  # unique per card: "<visit_id>:<alert_id>"
    summary: str = Field(max_length=140)
    detail: str
    indicator: Literal["info", "warning", "critical"]
    source: Source
    suggestions: List[Suggestion] = []
    selection_behavior: Literal["at-most-one", "any"] = Field(default="at-most-one", alias="selectionBehavior")
    override_reasons: List[Coding] = Field(default_factory=list, alias="overrideReasons")
    extension: CardExtension


# --- Visit check ------------------------------------------------------------------------


class VisitCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    note: str = Field(max_length=20000)
    use_ai: bool = True
    # The AI's management plan (the Streamlit "ARTEMIS Review" option); off by default, as there.
    include_plan: bool = False


class Plan(BaseModel):
    management_plan: Optional[str] = None
    issues: List[Dict[str, Any]] = []
    # Set when the plan step failed; generic, the details go to the server log.
    error: Optional[str] = None


class VisitCheckResponse(BaseModel):
    visit_id: str
    patient_id: str
    visit_date: str
    saved_at: str
    status: Status
    ai_review: AiReview
    model: Optional[str]
    cards: List[Card]
    plan: Optional[Plan]
    # False when the visit record couldn't be saved; the results are still shown, as in the app.
    record_saved: bool


# --- Decisions --------------------------------------------------------------------------


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    alert_id: str = Field(min_length=1, max_length=200)
    action: Action
    reason: Optional[OverrideReason] = None
    comment: str = Field(default="", max_length=2000)


class DecisionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    decisions: List[DecisionIn] = Field(min_length=1, max_length=100)


class DecisionOut(BaseModel):
    alert_id: str
    action: Action
    reason: str
    comment: str
    saved_at: str


class DecisionsResponse(BaseModel):
    visit_id: str
    # The latest decision on each alert that has one, in alert order.
    decisions: List[DecisionOut]
    all_resolved: bool
    unresolved: List[str]
