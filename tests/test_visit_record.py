"""Fix 9: each visit is saved: the checks when they run, and the clinician's decisions at Finalize."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from artemis.review import alert_resolution_ok
from tests import pipeline_harness as h


def _patient(pid: str) -> dict:
    return copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == pid))


def _lines(folder: Path) -> list:
    return [json.loads(line) for f in sorted(folder.glob("*.jsonl")) for line in f.read_text(encoding="utf-8").splitlines()]


def test_running_the_checks_saves_a_record(tmp_path: Path) -> None:
    p = _patient("P001")
    shown = h.run_patient(p, records_dir=tmp_path)
    lines = _lines(tmp_path)
    assert [e["event"] for e in lines] == ["checks_run"]
    e = lines[0]
    assert (e["patient_id"], e["visit_date"], e["note"]) == ("P001", p["today_encounter"]["date"], p["today_encounter"]["note"])
    assert (e["model"], e["ai_review"], e["status"]) == ("replay", "ok", shown["status"])
    assert e["app_version"] and e["visit_id"] and e["saved_at"]
    assert [(a["source"], a["title"], a["severity"]) for a in e["alerts"]] == [
        (a["source"], a["title"], (a["evidence"] or {}).get("severity")) for a in shown["alerts"]
    ]


def test_other_as_an_override_reason_needs_a_written_comment() -> None:
    state = {"alert_action_A1": "Override", "alert_override_reason_A1": "Other (say why)", "alert_override_comment_A1": "  "}
    assert not alert_resolution_ok(state, "A1")
    state["alert_override_comment_A1"] = "Done at another clinic last week."
    assert alert_resolution_ok(state, "A1")
    state["alert_override_reason_A1"] = "Already done, not documented"
    state["alert_override_comment_A1"] = ""
    assert alert_resolution_ok(state, "A1")


def test_the_override_reasons_are_the_designs_list() -> None:
    """Owner, 2026-11-26 ("A, design's list"): the list in docs/design/brief.md, in its order."""
    import re

    from artemis.review import OTHER_REASON, OVERRIDE_REASONS

    brief = (Path(__file__).resolve().parents[1] / "docs" / "design" / "brief.md").read_text(encoding="utf-8")
    proposed = re.search(r"Proposed: (.*?)(?:\r?\n){2}", brief, re.S).group(1)
    assert OVERRIDE_REASONS == [r.strip() for r in " ".join(proposed.split()).rstrip(".").split(" · ")]
    assert OVERRIDE_REASONS[-1] == OTHER_REASON == "Other (say why)"


def test_an_older_reason_still_shows_when_a_saved_visit_is_reopened() -> None:
    """Saved decisions keep the reason they were saved with; the picker keeps it selectable."""
    from artemis.review import OVERRIDE_REASONS, reason_options

    assert reason_options("") == ["", *OVERRIDE_REASONS]
    assert reason_options("Patient declined") == ["", *OVERRIDE_REASONS]
    assert reason_options("Already addressed") == ["", *OVERRIDE_REASONS, "Already addressed"]


def test_an_older_other_still_needs_its_comment() -> None:
    state = {"alert_action_A1": "Override", "alert_override_reason_A1": "Other", "alert_override_comment_A1": ""}
    assert not alert_resolution_ok(state, "A1")


def test_saved_results_come_back_exactly_as_they_were_shown(tmp_path: Path) -> None:
    from artemis import visit_record as vr

    shown = h.run_patient(_patient("P005"), records_dir=tmp_path)
    entries, unreadable = vr.read_entries(tmp_path, "P005")
    checks, finalized = vr.last_visit(entries)
    assert unreadable == 0 and finalized is None
    back = vr.restore(checks)
    assert h._plain(back["analysis_alerts"]) == shown["alerts"]
    assert [[c.chunk_id for c in r["retrieved"]] for r in back["analysis_results"]] == [r["retrieved"] for r in shown["results"]]
    assert [r["explanation"].text for r in back["analysis_results"]] == [r["explanation"] for r in shown["results"]]
    assert (back["analysis_status"], back["analysis_screening_outcome"]) == (shown["status"], shown["screening_outcome"])
    plan = back["agentic_debug_result"]
    assert (plan.updated_management_plan_text, plan.plan_issues) == (shown["plan_text"], shown["plan_issues"])


def test_a_half_written_line_is_counted_and_the_lines_after_it_still_read(tmp_path: Path) -> None:
    from artemis import visit_record as vr

    h.run_patient(_patient("P001"), records_dir=tmp_path)
    f = next(tmp_path.glob("*.jsonl"))
    with f.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "finalized", "visit_')  # the app stopped mid-write
    vr.append_entry(tmp_path, {"event": "finalized", "visit_id": "v2", "patient_id": "P001", "decisions": []})
    entries, unreadable = vr.read_entries(tmp_path, "P001")
    assert unreadable == 1
    assert [e["event"] for e in entries] == ["checks_run", "finalized"]


def test_a_patient_id_cannot_write_outside_the_records_folder(tmp_path: Path) -> None:
    from artemis import visit_record as vr

    folder = tmp_path / "records"
    entry = {"event": "checks_run", "visit_id": "v1", "patient_id": "../../evil"}
    path = vr.append_entry(folder, entry)
    assert path.parent == folder
    assert vr.read_entries(folder, "../../evil") == ([entry], 0)


def test_patients_whose_ids_look_alike_never_share_records(tmp_path: Path) -> None:
    from artemis import visit_record as vr

    for pid in ("a b", "a_b", "A B"):
        vr.append_entry(tmp_path, {"event": "checks_run", "visit_id": pid, "patient_id": pid})
    assert [e["patient_id"] for e in vr.read_entries(tmp_path, "a b")[0]] == ["a b"]
    assert len(list(tmp_path.glob("*.jsonl"))) == 3


def test_an_older_record_that_says_yellow_reopens_as_amber() -> None:
    """The owner renamed YELLOW to AMBER (2026-11-26). Saved lines are never rewritten, so an
    older one is read as AMBER where records are read."""
    from artemis import visit_record as vr

    old = {"event": "checks_run", "patient_id": "P001", "visit_id": "v", "status": "YELLOW", "alerts": [], "results": []}
    assert vr.restore(old)["analysis_status"] == "AMBER"


def test_a_reopened_visit_remembers_the_reason_it_was_saved_with() -> None:
    """The picker offers the saved reason from its own key, so switching away from an older
    reason doesn't change the picker's options mid-choice (which blanks it in Streamlit)."""
    from artemis import visit_record as vr
    from ui.state import clear_analysis

    alert = {"alert_id": "A1", "title": "t", "message": "m", "evidence": {}, "query_hint": "", "source": "rule"}
    checks = {"event": "checks_run", "patient_id": "P001", "visit_id": "v", "status": "AMBER",
              "alerts": [alert], "results": [{"retrieved": [], "explanation": {"text": "", "used_llm": False}}]}
    finalized = {"event": "finalized", "visit_id": "v", "patient_id": "P001", "saved_at": "2026-11-20T08:00:00+00:00",
                 "decisions": [{"alert_id": "A1", "action": "Override", "reason": "Already addressed", "comment": ""}]}
    values = vr.restore(checks, finalized)
    assert values["alert_saved_reason_A1"] == "Already addressed"
    assert values["alert_override_reason_A1"] == "Already addressed"
    clear_analysis(values)  # forgotten with the rest of the visit
    assert "alert_saved_reason_A1" not in values
