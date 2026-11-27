"""The AI management plan, made on demand for a saved visit ("Compare plans", plan B1/B2, 4C.4).

Owner's decisions (2026-11-27, docs/decisions.tsv): the plan step keeps its retries (decision 4);
a plan comes only from this route, never from the visit check (decision 5); checks and plans
count together toward one limit of 6 a minute (decision 6). The plan is saved in the database
and comes back in screen shape, as artemis/plan/view.py reads it, on this reply and when the
visit is reopened. The model is a stand-in (tests/api_fakes.py): nothing is spent.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from artemis.plan.view import read_plan
from tests.api_fakes import FakeModel, fake_search, replies_for

LOCAL = {"Origin": "http://localhost:3000"}
NOTE = "Routine follow-up. No issues. Continue TLD."
GENERIC = "The management plan could not be produced."


def _check(api, patient_id="P001", note=NOTE):
    r = api.client.post(f"/api/patients/{patient_id}/visits", json={"note": note}, headers=LOCAL)
    assert r.status_code == 200, r.text
    return r.json()


def _compare(api, visit_id):
    return api.client.post(f"/api/visits/{visit_id}/plan", headers=LOCAL)


def _plans(api):
    from backend.records import VisitPlan

    with Session(api.engine) as s:
        return list(s.exec(select(VisitPlan).order_by(VisitPlan.id)).all())


# The visit check no longer makes plans (decision 5)


def test_the_visit_check_makes_no_plan(api):
    body = _check(api)
    assert "plan" not in api.model.calls
    assert "plan" not in body  # the plan is this route's alone; a reopened visit carries the saved one
    assert _plans(api) == []


def test_the_visit_check_refuses_the_old_plan_switch(api):
    r = api.client.post("/api/patients/P001/visits", json={"note": NOTE, "include_plan": True}, headers=LOCAL)
    assert r.status_code == 422
    assert api.model.calls == []


# Making a plan


def test_compare_plans_sends_the_plan_in_screen_shape(api):
    visit = _check(api)
    api.model.calls.clear()
    r = _compare(api, visit["visit_id"])
    assert r.status_code == 200, r.text
    plan = r.json()
    assert "plan" in api.model.calls
    view = read_plan(replies_for("P001")["plan"], clinician_plan_written=True)
    assert plan["outcome"] == "made"
    assert plan["visit_id"] == visit["visit_id"]
    assert plan["model"] == "fake-model"
    assert plan["regimen"] == {"label": view.regimen_label, "tone": view.regimen_tone,
                               "text": view.regimen_text, "reason": view.regimen_reason}
    assert plan["items"] == [
        {"problem": i.problem, "action": i.action, "reason": i.reason, "verdict_label": i.verdict_label,
         "explanation": i.explanation}
        for i in view.items
    ]
    assert plan["items"] and plan["monitoring"] == view.monitoring and plan["counselling"] == view.counselling
    assert (plan["issues"], plan["issues_note"], plan["error"], plan["saved"]) == ([], None, None, True)


def test_the_plan_is_saved_and_comes_back_with_the_reopened_visit(api):
    visit = _check(api)
    made = _compare(api, visit["visit_id"]).json()
    rows = _plans(api)
    assert len(rows) == 1
    assert (rows[0].visit_id, rows[0].model, rows[0].outcome) == (visit["visit_id"], "fake-model", "made")
    assert rows[0].plan_text == replies_for("P001")["plan"]
    reopened = api.client.get(f"/api/visits/{visit['visit_id']}", headers=LOCAL).json()
    assert reopened["plan"] == made
    assert api.client.get(f"/api/visits/{_check(api)['visit_id']}", headers=LOCAL).json()["plan"] is None


def test_with_no_plan_in_the_note_every_item_says_there_is_nothing_to_compare(api):
    visit = _check(api, note="")
    plan = _compare(api, visit["visit_id"]).json()
    assert plan["items"] and {i["verdict_label"] for i in plan["items"]} == {"No plan to compare"}


def test_the_plan_is_made_for_the_visits_own_note(api):
    """The plan reads the note the check ran on, not the patient record's own note."""
    seen = []
    inner = api.model

    class Watching:
        model = "fake-model"
        calls = inner.calls

        def chat(self, messages, **kw):
            seen.append(" ".join(str(m.get("content")) for m in messages))
            return inner.chat(messages, **kw)

    visit = _check(api, note="Patient reports dizziness since Tuesday.")
    api.model = Watching()
    _compare(api, visit["visit_id"])
    assert seen and any("dizziness since Tuesday" in s for s in seen)


# Pressing it again (decision 7: "A, keep a good plan")


def test_pressing_again_shows_the_saved_plan_with_no_new_ai_call(api):
    visit = _check(api)
    first = _compare(api, visit["visit_id"]).json()
    api.model.calls.clear()
    again = _compare(api, visit["visit_id"])
    assert again.status_code == 200
    assert again.json() == first
    assert api.model.calls == [] and len(_plans(api)) == 1


def test_a_saved_plan_is_shown_even_when_the_search_or_model_is_down(api):
    """Showing a saved plan runs nothing, so it needs neither."""
    visit = _check(api)
    first = _compare(api, visit["visit_id"]).json()
    broken = fake_search(ready=False)
    api.services.search = lambda: broken
    api.model = None
    assert _compare(api, visit["visit_id"]).json() == first


def test_after_a_failed_plan_pressing_again_tries_again(api):
    visit = _check(api)
    good = api.model
    api.model = FakeModel({}, fail=True)
    assert _compare(api, visit["visit_id"]).json()["outcome"] == "failed"
    api.model = good
    good.calls.clear()
    retried = _compare(api, visit["visit_id"]).json()
    assert retried["outcome"] == "made" and "plan" in good.calls
    assert [p.outcome for p in _plans(api)] == ["failed", "made"]
    assert api.client.get(f"/api/visits/{visit['visit_id']}", headers=LOCAL).json()["plan"] == retried


def test_a_plan_that_failed_the_apps_checks_is_shown_and_pressing_again_tries_again(api):
    """A readable plan the app's checks flagged is shown with the warning, but it isn't a good plan
    to keep: pressing again tries again (code review, 2026-11-27: an empty "{}" plan was kept)."""
    from artemis.screen_text import PLAN_ISSUES_NOTE

    visit = _check(api)
    api.model = FakeModel({**replies_for("P001"), "plan": "{}"})
    flagged = _compare(api, visit["visit_id"]).json()
    assert flagged["outcome"] == "made" and flagged["issues"] and flagged["issues_note"] == PLAN_ISSUES_NOTE
    api.model = FakeModel(replies_for("P001"))
    retried = _compare(api, visit["visit_id"]).json()
    assert "plan" in api.model.calls
    assert retried["outcome"] == "made" and retried["issues"] == []
    assert len(_plans(api)) == 2


@pytest.mark.parametrize("odd", ['{"problems": 5}', '{"problems": true}'])
def test_odd_ai_output_never_breaks_the_reply(api, odd):
    visit = _check(api)
    api.model = FakeModel({**replies_for("P001"), "plan": odd})
    r = _compare(api, visit["visit_id"])
    assert r.status_code == 200, r.text
    assert len(_plans(api)) == 1


def test_a_model_server_that_does_not_answer_is_logged_by_kind_only(api, caplog):
    import logging

    visit = _check(api)
    api.model = FakeModel({}, fail=True)
    with caplog.at_level(logging.WARNING, logger="backend.main"):
        _compare(api, visit["visit_id"])
    lines = [r.getMessage() for r in caplog.records if r.name == "backend.main"]
    assert any(line.startswith("Plan not made:") for line in lines), lines
    assert not any("connection refused" in line for line in lines)


# When no plan can be made


def test_a_plan_the_ai_could_not_make_says_so_generically(api):
    visit = _check(api)
    api.model = FakeModel({}, fail=True)
    r = _compare(api, visit["visit_id"])
    assert r.status_code == 200, r.text
    plan = r.json()
    assert (plan["outcome"], plan["error"], plan["regimen"], plan["items"]) == ("failed", GENERIC, None, [])
    assert "connection refused" not in r.text  # the details go to the server log only
    assert _plans(api)[0].outcome == "failed"


def test_a_broken_plan_comes_back_with_its_issue_codes(api):
    visit = _check(api)
    api.model = FakeModel({**replies_for("P001"), "plan": "not json at all"})
    plan = _compare(api, visit["visit_id"]).json()
    assert plan["outcome"] == "failed" and plan["error"] == GENERIC
    assert plan["issues"] and all(isinstance(i, str) for i in plan["issues"])
    assert api.model.calls.count("plan") == 3  # the first try, a retry, and a repair pass (decision 4)


def test_a_readable_plan_that_failed_the_apps_checks_is_shown_with_the_warning():
    """After its retries the plan step can still hand back a readable plan that failed a check
    (for example, a problem with no verdict): it is shown, with the screen's warning (fix 7)."""
    import datetime

    from artemis.screen_text import PLAN_ISSUES_NOTE
    from backend.plans import plan_reply
    from backend.records import VisitPlan

    row = VisitPlan(visit_id="v1", made_at=datetime.datetime(2026, 11, 27, tzinfo=datetime.timezone.utc),
                    model="m", outcome="made", plan_text=replies_for("P001")["plan"],
                    issues=["problem_0_missing_key:clinician_plan_for_this_problem"])
    plan = plan_reply(row, note=NOTE)
    assert (plan.outcome, plan.issues_note, plan.error) == ("made", PLAN_ISSUES_NOTE, None)
    assert plan.issues == ["problem_0_missing_key:clinician_plan_for_this_problem"] and plan.items


def test_no_such_visit(api):
    r = _compare(api, "nope")
    assert r.status_code == 404
    assert r.json() == {"detail": "No such visit."}
    assert api.model.calls == []


def test_with_the_guideline_search_down_no_plan_is_made(api):
    """G33: no plan rests on passages a search that didn't load would give."""
    visit = _check(api)
    api.model.calls.clear()
    broken = fake_search(ready=False)
    api.services.search = lambda: broken
    r = _compare(api, visit["visit_id"])
    assert r.status_code == 503
    assert r.json() == {"detail": "The guideline search is unavailable, so no plan was made."}
    assert api.model.calls == [] and _plans(api) == []


def test_with_no_model_server_no_plan_is_made(api):
    visit = _check(api)
    api.model = None
    r = _compare(api, visit["visit_id"])
    assert r.status_code == 503
    assert r.json() == {"detail": "No AI model server is set up."}
    assert _plans(api) == []


def test_a_plan_that_could_not_be_saved_is_still_shown(api, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from backend import records

    visit = _check(api)

    def broken(*_a, **_k):
        raise OperationalError("insert", {}, Exception("database went away"))

    monkeypatch.setattr(records, "save_plan", broken)
    r = _compare(api, visit["visit_id"])
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "made" and r.json()["saved"] is False
    assert "database went away" not in r.text


# One limit for checks and plans (decision 6)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def limited(api):
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.settings import Settings

    api.services.clock = FakeClock()
    api.app = create_app(settings=Settings(visit_checks_per_minute=3), services=api.services)
    api.client = TestClient(api.app, base_url="http://localhost")
    with api.client:
        yield api


def test_checks_and_plans_share_one_limit(limited):
    first, second = _check(limited)["visit_id"], _check(limited)["visit_id"]
    assert _compare(limited, first).status_code == 200  # the third use this minute
    calls, saved = len(limited.model.calls), len(_plans(limited))
    r = _compare(limited, second)
    assert r.status_code == 429
    assert r.json() == {"detail": "Too many visit checks: wait a moment and try again."}
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert len(limited.model.calls) == calls and len(_plans(limited)) == saved  # nothing run, nothing spent
    assert limited.client.post("/api/patients/P001/visits", json={"note": NOTE}, headers=LOCAL).status_code == 429


def test_a_plan_refused_before_it_runs_does_not_use_up_the_limit(limited):
    visit = _check(limited)["visit_id"]
    broken = fake_search(ready=False)
    search = limited.services.search
    limited.services.search = lambda: broken
    for _ in range(3):
        assert _compare(limited, visit).status_code == 503
    assert _compare(limited, "nope").status_code == 404
    limited.services.search = search
    assert _check(limited)["visit_id"] and _check(limited)["visit_id"]  # uses 2 and 3 of 3


def test_showing_a_saved_plan_does_not_use_up_the_limit(limited):
    visit = _check(limited)["visit_id"]
    assert _compare(limited, visit).status_code == 200  # 2 of 3
    for _ in range(5):
        assert _compare(limited, visit).status_code == 200  # the saved plan, nothing run
    assert _check(limited)["visit_id"]  # 3 of 3


# An "Uncertain" plan is flagged (owner, 2026-11-27: "Yes, flag it"): found in a live visit, a plan
# that said it lacked data was kept as good and never asked for again.


def _uncertain_plan_text():
    import json

    plan = json.loads(replies_for("P001")["plan"])
    plan["art_regimen_decision"] = {"decision": "Uncertain", "reason": "Not enough information."}
    return json.dumps(plan)


def test_an_uncertain_regimen_verdict_flags_the_plan():
    import datetime

    from artemis.plan.flow import AgenticResult
    from artemis.screen_text import PLAN_ISSUES_NOTE
    from backend.plans import is_good, plan_reply, plan_row

    row = plan_row(AgenticResult(updated_management_plan_text=_uncertain_plan_text(), plan_issues=[]), visit_id="v1",
                   model="m", made_at=datetime.datetime(2026, 11, 27, tzinfo=datetime.timezone.utc))
    assert row.outcome == "made" and "flag:regimen_uncertain" in row.issues
    assert not is_good(row)
    reply = plan_reply(row, note=NOTE)
    assert reply.regimen.label == "Needs review" and reply.issues_note == PLAN_ISSUES_NOTE


def test_a_clear_regimen_verdict_is_not_flagged():
    import datetime

    from artemis.plan.flow import AgenticResult
    from backend.plans import is_good, plan_row

    row = plan_row(AgenticResult(updated_management_plan_text=replies_for("P001")["plan"], plan_issues=[]), visit_id="v1",
                   model="m", made_at=datetime.datetime(2026, 11, 27, tzinfo=datetime.timezone.utc))
    assert row.issues == [] and is_good(row)


def test_pressing_again_after_an_uncertain_plan_asks_the_ai_again(api):
    visit = _check(api)
    api.model = FakeModel({**replies_for("P001"), "plan": _uncertain_plan_text()})
    first = _compare(api, visit["visit_id"]).json()
    assert first["outcome"] == "made" and "flag:regimen_uncertain" in first["issues"]
    api.model.calls.clear()
    _compare(api, visit["visit_id"])
    assert "plan" in api.model.calls and len(_plans(api)) == 2
