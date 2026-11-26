"""A limit on repeated visit checks (owner, 2026-11-26: at most 6 a minute).

Each check can call the paid AI, so a page stuck in a loop must stop spending within a minute.
A refused check runs nothing and spends nothing. The clock here is a stand-in, so no test waits.
"""

from __future__ import annotations

from sqlmodel import Session, select

LOCAL = {"Origin": "http://localhost:3000"}
NOTE = {"note": "Routine follow-up."}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _with_clock(api, clock):
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.settings import Settings

    api.services.clock = clock
    api.app = create_app(settings=Settings(), services=api.services)
    api.client = TestClient(api.app, base_url="http://localhost")
    return api.client


def _checks(api):
    from backend.records import VisitCheck

    with Session(api.engine) as s:
        return len(s.exec(select(VisitCheck)).all())


def test_six_checks_a_minute_then_wait(api):
    clock = FakeClock()
    client = _with_clock(api, clock)
    for _ in range(6):
        assert client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL).status_code == 200
    calls, saved = len(api.model.calls), _checks(api)
    r = client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL)
    assert r.status_code == 429
    assert r.json() == {"detail": "Too many visit checks: wait a moment and try again."}
    assert 1 <= int(r.headers["retry-after"]) <= 60
    assert len(api.model.calls) == calls and _checks(api) == saved  # nothing run, nothing spent


def test_the_limit_frees_up_as_the_minute_passes(api):
    clock = FakeClock()
    client = _with_clock(api, clock)
    for _ in range(6):
        client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL)
        clock.now += 5
    assert client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL).status_code == 429
    clock.now += 31  # the first check is now more than a minute old
    assert client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL).status_code == 200


def test_a_refused_request_does_not_use_up_the_limit(api):
    """A check refused for another reason (bad body, unknown patient) isn't counted."""
    clock = FakeClock()
    client = _with_clock(api, clock)
    for _ in range(10):
        assert client.post("/api/patients/NOPE/visits", json=NOTE, headers=LOCAL).status_code == 404
        assert client.post("/api/patients/P001/visits", json={}, headers=LOCAL).status_code == 422
    assert client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL).status_code == 200


def test_other_routes_are_not_limited(api):
    clock = FakeClock()
    client = _with_clock(api, clock)
    for _ in range(6):
        client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL)
    for _ in range(20):
        assert client.get("/api/patients", headers=LOCAL).status_code == 200
    assert client.get("/api/clinic-day", headers=LOCAL).status_code == 200


def test_the_limit_is_a_setting(monkeypatch):
    from backend.settings import settings_from_env

    monkeypatch.delenv("ARTEMIS_VISIT_CHECKS_PER_MINUTE", raising=False)
    assert settings_from_env().visit_checks_per_minute == 6
    monkeypatch.setenv("ARTEMIS_VISIT_CHECKS_PER_MINUTE", "2")
    assert settings_from_env().visit_checks_per_minute == 2


def test_a_lower_setting_is_obeyed(api):
    from fastapi.testclient import TestClient

    from backend.main import create_app
    from backend.settings import Settings

    api.services.clock = FakeClock()
    client = TestClient(create_app(settings=Settings(visit_checks_per_minute=2), services=api.services), base_url="http://localhost")
    assert [client.post("/api/patients/P001/visits", json=NOTE, headers=LOCAL).status_code for _ in range(3)] == [200, 200, 429]


import pytest  # noqa: E402


@pytest.mark.parametrize("bad", ["0", "-3", "six"])
def test_a_limit_below_one_or_not_a_number_is_refused_at_start(monkeypatch, bad):
    """Checked once where the setting is read: 0 made every visit check fail with a 500 (review)."""
    from backend.settings import settings_from_env

    monkeypatch.setenv("ARTEMIS_VISIT_CHECKS_PER_MINUTE", bad)
    with pytest.raises(ValueError, match="ARTEMIS_VISIT_CHECKS_PER_MINUTE"):
        settings_from_env()


def test_the_limiter_itself_refuses_a_limit_below_one():
    from backend.limits import SlidingWindow

    with pytest.raises(ValueError):
        SlidingWindow(0, 60.0, lambda: 0.0)
