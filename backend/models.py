"""The shapes the backend reads and returns (plan item 4.1).

Requests forbid unknown fields, so a field the screen doesn't show is refused rather than
quietly used (ACCESS.md section 5). Alerts go out as CDS Hooks cards
(https://cds-hooks.hl7.org/2.0/#cds-service-response): summary, detail, indicator, source,
suggestions and overrideReasons, with ARTEMIS's own fields under `extension`.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from artemis.patient.new_case import MAX_NOTE, MAX_PREVIOUS_ART, VISIT_TYPES
from artemis.review import OVERRIDE_REASONS
from artemis.statuses import AI_REVIEW_OUTCOMES, STATUSES

# Built from the one list in artemis/review.py, which the decision rules use too, so the two can't drift apart.
OverrideReason = Literal[tuple(OVERRIDE_REASONS)]  # type: ignore[valid-type]

# Built from artemis/visit.py's lists, which docs/screen-checklist.md covers one by one (plan 4.7).
Status = Literal[STATUSES]  # type: ignore[valid-type]
AiReview = Literal[AI_REVIEW_OUTCOMES]  # type: ignore[valid-type]  # how the AI review ended
VisitType = Literal[VISIT_TYPES]  # type: ignore[valid-type]  # owner, 2026-11-26
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
    name: Optional[str] = ""
    sex: Optional[str] = ""  # saved as null when the form leaves it blank
    age_years: Optional[int] = None
    art_regimen_current: List[str] = []
    other_medications: List[str] = []
    regimen_history: List[Dict[str, Any]] = []
    intake: Dict[str, Any] = {}
    visits: List[Dict[str, Any]] = []
    labs: Dict[str, List[Dict[str, Any]]] = {}
    today_encounter: TodayEncounter


class NewLabRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test: str = Field(max_length=40)  # from artemis.patient.labs.TEST_UNITS, e.g. "creatinine"
    date: str = Field(max_length=10)  # YYYY-MM-DD
    value: str = Field(max_length=40)  # as written, e.g. "<50"; must hold a number
    unit: str = Field(default="", max_length=20)  # one of the test's units; blank means its usual one
    when: Literal["today", "previous"]


class PreviousArtIn(BaseModel):
    """One regimen the patient took before, with when it started and ended."""

    model_config = ConfigDict(extra="forbid")

    regimen: List[Annotated[str, Field(max_length=20)]] = Field(max_length=20)  # picks from the app's list, e.g. "TLE"
    start_date: datetime.date  # YYYY-MM-DD
    end_date: datetime.date  # YYYY-MM-DD, by the visit date


class NewCase(BaseModel):
    """A new made-up patient case (owner, 2026-11-26: the old Streamlit form's fields and rules,
    plus an optional name). Checked again by artemis.patient.new_case, which builds the record."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(max_length=40)
    name: Optional[str] = Field(default=None, max_length=5000)
    age_years: Optional[int] = None
    sex: Optional[Literal["M", "F"]] = None
    art_regimen: List[Annotated[str, Field(max_length=20)]] = Field(default=[], max_length=20)  # picks from the app's list, e.g. "TLD"
    other_medications: List[Annotated[str, Field(max_length=200)]] = Field(default=[], max_length=50)  # one per item
    complaints: str = Field(default="", max_length=5000)
    examination_findings: str = Field(default="", max_length=5000)
    prior_history: str = Field(default="", max_length=5000)
    labs: List[NewLabRow] = Field(default=[], max_length=50)
    # Today's visit (owner, 2026-11-26): its date (today when left out), its type, and the note.
    visit_date: Optional[datetime.date] = None
    visit_type: Optional[VisitType] = None
    todays_note: str = Field(default="", max_length=MAX_NOTE)
    previous_art: List[PreviousArtIn] = Field(default=[], max_length=MAX_PREVIOUS_ART)
    # The case's appointment on its visit date, HH:MM in 24-hour time (owner, 2026-11-27).
    appointment_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class PatientSummary(BaseModel):
    """One row of the patient list."""

    patient_id: str
    name: str
    sex: str
    age_years: Optional[int]
    art_regimen_current: List[str]
    visit_date: str


class LabResult(BaseModel):
    """One lab result in the unit it was recorded in, never converted (owner, 2026-11-26)."""

    date: str  # YYYY-MM-DD
    value: str  # as typed, for example "<50"
    unit: str  # for example "umol/L" or "mg/dL"
    source: str  # "today", "previous" or "record" (older records say neither)


class LabNote(BaseModel):
    """Lab results typed as free text into the old add-case boxes; shown as text, never read as numbers."""

    date: Optional[str]
    source: str
    text: str


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
    # Each test's results, oldest first, read by artemis.patient.labs.read_lab_entries: the one
    # place stored results are read, older value_umol_per_l-style keys included.
    labs: Dict[str, List[LabResult]]
    lab_notes: List[LabNote]
    today_encounter: Dict[str, Any]


# --- The demo clinic day --------------------------------------------------------------------


class Booking(BaseModel):
    """One appointment in the schedule file."""

    time: str = Field(pattern=r"^\d{2}:\d{2}$")  # HH:MM, the clinic's local time
    patient_id: str = Field(min_length=1, max_length=200)
    name: Optional[str] = None  # shown only when the patient's record has no name


class ClinicDaySchedule(BaseModel):
    """A clinic day's schedule to load (the demo day, tests/fixtures/clinic_day.json), checked when it is read."""

    clinic: str
    room: str
    clinician: str
    date: datetime.date
    appointments: List[Booking] = Field(min_length=1)


BoardState = Literal["waiting", "needs_you", "done"]  # the design's Waiting / Needs you / Done


class Appointment(BaseModel):
    """One row of the day board: the booking, and the state of the patient's latest saved check."""

    time: str
    patient_id: str
    name: str
    age_years: Optional[int]
    sex: str
    regimen: str  # for example "TDF/3TC/DTG"
    state: BoardState  # waiting: no check yet; needs_you: latest check not finalized; done: finalized
    visit_id: Optional[str]
    status: Optional[Status]
    ai_review: Optional[AiReview]
    ai_review_label: Optional[str]  # None while waiting
    ai_review_card_label: Optional[str]  # the board's note; None while waiting or when it finished cleanly
    alert_count: int
    reviewed_count: int  # alerts with a saved decision
    finalized_at: Optional[str]


class DayCounts(BaseModel):
    booked: int
    checked: int
    finalized: int
    left_in_red: int  # latest check RED and not finalized


class ClinicDay(BaseModel):
    clinic: str
    room: str
    clinician: str
    date: str  # YYYY-MM-DD
    appointments: List[Appointment]
    counts: DayCounts
    # The clinic days just before and after this one, so the board can step between days.
    previous_date: Optional[str] = None
    next_date: Optional[str] = None


# --- The add-case form's pick lists ------------------------------------------------------


class RegimenChoice(BaseModel):
    choice: str  # what the form shows and sends back, e.g. "TLD" or "DTG"
    drugs: List[str]  # what it is saved as, e.g. ["TDF", "3TC", "DTG"]


class LabTestChoice(BaseModel):
    test: str  # what the form sends back, e.g. "creatinine"
    name: str  # the name in a sentence, e.g. "creatinine", "eGFR"
    label: str  # the name in a list, with a leading capital: "Creatinine", "eGFR" (artemis/patient/labs.py TEST_LABELS)
    units: List[str]  # the usual unit first


class FormChoices(BaseModel):
    """The add-case form's lists, the same ones the add-case route accepts (owner, 2026-11-26)."""

    art_regimens: List[RegimenChoice]  # combinations first, then single drugs
    lab_tests: List[LabTestChoice]
    visit_types: List[str]


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
    page_number: Optional[int] = None  # the guideline's printed page (G36)
    # The screen's citation, e.g. "Uganda HIV Guidelines 2022 · p. 255" (screen_text.citation_line).
    citation: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AlertValue(_CdsOut):
    """One patient value an alert is about, as recorded (the design's '52 eGFR' box)."""

    label: str  # e.g. "eGFR"
    value: str  # as recorded, e.g. "52" or "<50"
    unit: str
    date: str  # YYYY-MM-DD


class CardExtension(_CdsOut):
    alert_id: str  # the alert's own id, which decisions refer to
    kind: AlertKind
    severity: Optional[str] = None
    explanation: str = ""
    passages: List[Passage] = []
    # The screen's own words (artemis/screen_text.py): "Alert (Rule check): ...", and the
    # reference list with its heading.
    heading: str
    references_heading: str
    references: List[str] = []
    # By code, no AI change (owner, 2026-11-26): the lab values the alert is about, and the one
    # guideline sentence closest to it (None when none is close enough).
    values: List[AlertValue] = []
    key_sentence: Optional[str] = None


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


class Banner(BaseModel):
    """One coloured banner above a visit's results (screen_text.status_banners)."""

    level: Literal["success", "info", "warning", "error"]  # green, blue, amber, red
    text: str


class VisitCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    note: str = Field(max_length=20000)
    use_ai: bool = True
    # No plan here: a plan is made only by "Compare plans" (owner, 2026-11-27: "A, only Compare plans").


# --- The management plan ("Compare plans", plan B1/B2) -------------------------------------
# Sent as artemis/plan/view.py reads the AI's plan: only what the AI actually said.

PlanOutcome = Literal["made", "failed"]  # failed: no readable plan came back


class PlanRegimen(BaseModel):
    """The ART regimen decision: its badge (label and tone) and the AI's own words."""

    label: str  # "Switch", "Hold temporarily", "Continue" or "Needs review"
    tone: Literal["red", "amber", "green", "grey"]
    text: str  # the AI's decision as written
    reason: str


class PlanItem(BaseModel):
    """One problem: what the AI suggests, and how it compares with the clinician's note."""

    problem: str
    action: str
    reason: str
    # "Matches your plan", "Differs from your plan", "Partly in your plan", "Not in your plan",
    # "Not assessed", or "No plan to compare" when the note had no plan.
    verdict_label: str
    explanation: str


class ManagementPlan(BaseModel):
    visit_id: str
    made_at: str
    model: Optional[str]
    outcome: PlanOutcome
    regimen: Optional[PlanRegimen]  # None when the plan failed
    items: List[PlanItem]
    monitoring: List[str]
    counselling: List[str]
    # What the plan failed in the app's own checks, as the plan step's short codes ("invalid_json",
    # "cut_off"), and the screen's warning sentence for them (artemis/screen_text.py).
    issues: List[str]
    issues_note: Optional[str]
    error: Optional[str]  # generic when the plan failed; the details go to the server log only
    saved: bool  # False when it couldn't be saved; it is still shown


class VisitCheckResponse(BaseModel):
    visit_id: str
    patient_id: str
    visit_date: str
    saved_at: str
    status: Status
    ai_review: AiReview
    # How the AI review ended, in the screens' words (artemis/screen_text.py): the record label,
    # and the day board's short label (None when the review finished cleanly).
    ai_review_label: str
    ai_review_card_label: Optional[str]
    model: Optional[str]
    cards: List[Card]
    # False when the visit record couldn't be saved; the results are still shown, as in the app.
    record_saved: bool
    # The screen's own words for this result (artemis/screen_text.py), shown as they are.
    banners: List[Banner]
    disclaimer: str
    finalize_note: Optional[str]  # FINALIZE_BLOCKED while an alert waits for a decision


# --- Decisions --------------------------------------------------------------------------
# (SavedVisit, below the decision shapes, is a visit check reopened with its decisions.)


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
    finalize_note: Optional[str]  # FINALIZE_BLOCKED while an alert waits for a decision
    # When the visit was finalized; None while open, including after a later decision reopened it.
    finalized_at: Optional[str]


class SavedVisit(VisitCheckResponse):
    """A saved visit reopened (no new AI call): the check as it was shown, plus what was decided."""

    note: str
    decisions: List[DecisionOut]  # the latest decision on each decided alert, in alert order
    all_resolved: bool
    unresolved: List[str]
    finalized_at: Optional[str]  # None while open, including after a later decision reopened it
    plan: Optional[ManagementPlan]  # the latest plan "Compare plans" made, None before the first


class VisitSummary(BaseModel):
    """One of a patient's past checks, newest first."""

    visit_id: str
    visit_date: str
    saved_at: str
    status: Status
    ai_review: AiReview
    ai_review_label: str
    ai_review_card_label: Optional[str]
    model: Optional[str]
    alert_count: int
    decided_count: int
    finalized_at: Optional[str]


class FinalizeRequest(BaseModel):
    """Finalize takes no fields: the time is the server's, the decisions are the saved ones."""

    model_config = ConfigDict(extra="forbid")


class FinalizeResponse(BaseModel):
    visit_id: str
    finalized_at: str
    decisions: List[DecisionOut]  # the decision on each alert as finalized, in alert order
