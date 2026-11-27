"""The evaluation through the backend itself (plan 4C.5, owner 2026-11-27: "A, through the backend").

Each case's patient goes into a throwaway database the way the app stores patients; the run
presses "run checks" and then "Compare plans" through the backend's own routes, and the record is
read back from what the backend saved. So the scores are the app's own behaviour. The model and
the search are stand-ins (tests/api_fakes.py): nothing is sent or spent.
"""

from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from artemis.ai.client import ChatReply
from artemis.evaluation.cases import load_cases
from tests.api_fakes import FakeModel, fake_search, replies_for

ROOT = Path(__file__).resolve().parents[1]
RECORD_KEYS = {"case_id", "model", "model_id", "repeat", "temperature", "seconds", "calls", "cost_usd", "status",
               "screening_outcome", "alerts", "retrieved", "screening", "plan_text", "plan_issues"}


def _case(case_id: str):
    return next(c for c in load_cases(ROOT / "eval" / "cases") if c.case_id == case_id)


def _run(case, client, rag=None, **kw):
    from backend.evaluation import run_case

    return run_case(case, client, rag or fake_search(), label="stub", repeat=kw.pop("repeat", 1), **kw)


class Priced(FakeModel):
    """The stand-in model, with a cost on every call, as a paid server reports it."""

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        reply = super().chat(messages, format=format, options_override=options_override)
        return ChatReply(reply.text, finish_reason=reply.finish_reason, error=reply.error,
                         usage={"prompt_tokens": 100, "completion_tokens": 10, "cost": 0.001})


def test_a_case_gives_what_the_app_gives_for_its_patient():
    """The same alerts, passages, status and plan as the backend's own two steps on that patient."""
    from artemis.visit import AnalysisOptions, management_plan, run_visit_analysis

    case = _case("P001")
    rec = _run(case, FakeModel(replies_for("P001")))
    note = case.patient["today_encounter"]["note"]
    direct = run_visit_analysis(patient=copy.deepcopy(case.patient), today_note=note, rag=fake_search(),
                                llm_client=FakeModel(replies_for("P001")),
                                options=AnalysisOptions(top_k=5, use_llm=True))
    plan = management_plan(patient=copy.deepcopy(case.patient), today_note=note, rag=fake_search(),
                           llm_client=FakeModel(replies_for("P001")))
    assert rec["alerts"] == json.loads(json.dumps([asdict(a) for a in direct.alerts], default=str))
    assert rec["retrieved"] == {r["alert"].alert_id: [c.chunk_id for c in r["retrieved"]] for r in direct.results}
    assert (rec["status"], rec["screening_outcome"]) == (direct.status, direct.screening_outcome)
    assert rec["screening"]["parse_status"] == direct.screening_debug["parse_status"]
    assert rec["plan_text"] == plan.updated_management_plan_text and rec["plan_issues"] == plan.plan_issues


def test_a_record_holds_what_the_scoring_needs():
    from artemis.evaluation.scoring import score_run

    case = _case("P001")
    rec = _run(case, FakeModel(replies_for("P001")), temperature=0.0)
    assert set(rec) == RECORD_KEYS
    assert (rec["case_id"], rec["model"], rec["model_id"], rec["repeat"]) == ("P001", "stub", "fake-model", 1)
    assert rec["temperature"] == 0  # the value used, never None
    assert "creatinine_overdue" in score_run(case, rec["alerts"]).caught
    json.dumps(rec)  # everything in it can be saved


def test_the_calls_and_the_cost_cover_the_check_and_the_plan():
    model = Priced(replies_for("P001"))
    rec = _run(_case("P001"), model)
    assert "plan" in model.calls and "screening" in model.calls
    assert len(rec["calls"]) == len(model.calls)
    assert rec["cost_usd"] == pytest.approx(0.001 * len(model.calls))


def test_every_repeat_is_a_visit_of_its_own_with_its_own_plan():
    """Pressing "Compare plans" again reuses a good plan (owner, 2026-11-27); a repeat is a new
    visit, so each repeat makes its own plan and spends its own calls."""
    model = FakeModel(replies_for("P001"))
    _run(_case("P001"), model, repeat=1)
    _run(_case("P001"), model, repeat=2)
    assert model.calls.count("plan") == 2


def test_with_the_search_down_there_is_no_plan():
    rec = _run(_case("P001"), FakeModel(replies_for("P001")), rag=fake_search(ready=False))
    assert rec["screening_outcome"] == "search_unavailable"
    assert (rec["plan_text"], rec["plan_issues"]) == (None, [])


def test_the_patient_is_read_back_from_the_database_as_the_app_reads_it():
    """A lab in the record's older shape comes back as value and unit, and the check still finds it."""
    case = _case("P001")
    assert "value_umol_per_l" in json.dumps(case.patient["labs"])  # the case file's older shape
    rec = _run(case, FakeModel(replies_for("P001")))
    assert any("creatinine" in (a["title"] or "").lower() for a in rec["alerts"])


def test_a_case_the_database_cannot_hold_is_refused_before_anything_runs():
    from backend.patients_db import UnplacedField

    case = copy.deepcopy(_case("P001"))
    case.patient["favourite_colour"] = "blue"
    model = FakeModel(replies_for("P001"))
    with pytest.raises(UnplacedField):
        _run(case, model)
    assert model.calls == []


def test_a_refused_request_stops_the_run():
    """The run stops loudly rather than saving a record of a check that never ran."""
    from backend.evaluation import RunFailed

    case = copy.deepcopy(_case("P001"))
    case.patient["today_encounter"]["note"] = "x" * 20001  # over the visit check's limit
    with pytest.raises(RunFailed, match="422"):
        _run(case, FakeModel(replies_for("P001")))


def test_patients_read_as_the_app_reads_them():
    """The search check (scripts/check_retrieval.py) reads each case's patient back from a throwaway
    database, as the app does: a lab in the older shape comes back as value and unit."""
    from backend.evaluation import as_the_app_reads

    case = _case("P001")
    back = as_the_app_reads([case.patient])
    assert [p["patient_id"] for p in back] == ["P001"]
    assert back[0]["labs"]["creatinine"] == [{"date": "2024-10-01", "value": "88", "unit": "umol/L", "source": "record"}]
    assert "expected_demo_outcome" not in back[0]  # the answer key stays with the evaluation
