from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_baseline", ROOT / "scripts" / "run_baseline.py")
rb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rb)  # type: ignore[union-attr]


def _plan(problems: list) -> SimpleNamespace:
    text = "Here is the plan:\n" + json.dumps({"problems": problems}) + "\nDone."
    return SimpleNamespace(updated_management_plan_text=text)


def test_plan_items_keeps_missing_verdict_as_none() -> None:
    items = rb._plan_items(
        _plan(
            [
                {"action": "Check creatinine", "reason": "On TDF"},
                {
                    "action": "Repeat viral load",
                    "reason": "Due",
                    "clinician_plan_for_this_problem": {"decision": "Gap"},
                },
            ]
        )
    )
    assert [i["model_decision"] for i in items] == [None, "Gap"]
    assert items[0]["action"] == "Check creatinine"


def test_plan_items_reports_unreadable_plan_and_empty_when_absent() -> None:
    assert rb._plan_items(SimpleNamespace(updated_management_plan_text="{not json}")) == [{"parse_error": True}]
    assert rb._plan_items(None) == []
    assert rb._plan_items({"error": "boom"}) == []


def test_scrub_removes_server_address_and_local_paths() -> None:
    local = str(ROOT) + os.sep + "Data" + os.sep + "x.md"
    data = {"err": "Connection to http://10.0.0.9:8000/v1 refused", "path": local, "n": 3}
    out = rb._scrub(data, ["http://10.0.0.9:8000/v1", "10.0.0.9:8000", "10.0.0.9"])
    assert "10.0.0.9" not in json.dumps(out)
    assert out["path"] == "Data" + os.sep + "x.md"
    assert out["n"] == 3


def test_safe_name_keeps_files_inside_the_folder() -> None:
    assert rb._safe_name("Kintu-Test 001") == "Kintu-Test_001"
    assert "/" not in rb._safe_name("../../etc/passwd")
    assert "\\" not in rb._safe_name("..\\..\\x")


def test_the_baseline_script_runs_a_patient_end_to_end(monkeypatch, tmp_path) -> None:
    # Phase 1 moved code out of app.py; the script must still run (it crashed on app.run_alerts).
    from tests import pipeline_harness as h

    monkeypatch.setenv("ARTEMIS_VISIT_RECORDS_DIR", str(tmp_path))
    patient = next(p for p in h.patients() if p["patient_id"] == "P001")
    client = h.ReplayClient(h._load("replies.json")["P001"])
    monkeypatch.setattr(rb.app, "_get_rag_engine", lambda **_: h.RagEngine(
        project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore(h._load("corpus.json"))))
    monkeypatch.setattr(rb.app, "openai_compat_config_from_env", lambda: h._ReplayConfig())
    monkeypatch.setattr(rb.app, "OpenAICompatClient", lambda _cfg: client)
    saved_st = rb.app.st
    try:
        out = rb.run_one(patient)
    finally:
        rb.app.st = saved_st
    assert out["patient_id"] == "P001"
    assert [a["title"] for a in out["rule_alerts"]] == ["Creatinine monitoring overdue while on TDF"]
    assert out["alerts"] and out["overall_status"] == "YELLOW"
