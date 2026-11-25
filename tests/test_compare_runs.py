from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("compare_runs", ROOT / "scripts" / "compare_runs.py")
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)  # type: ignore[union-attr]


def _run(pid: str = "P1", repeat: int = 1) -> dict:
    return {
        "patient_id": pid,
        "repeat": repeat,
        "overall_status": "YELLOW",
        "llm_error": None,
        "rule_alerts": [{"title": "Creatinine overdue"}],
        "alerts": [{"title": "Missing VL", "evidence": {"type": "llm_screening"}}],
        "plan_items": [{"action": "x", "model_decision": None}],
        "results": [{"retrieved": [{"metadata": {"source_path": "Data\\MarkDown Files\\UG.md"}}]}],
    }


def _folder(tmp: Path, name: str, runs: list) -> Path:
    d = tmp / name
    d.mkdir()
    for r in runs:
        (d / f"{r['patient_id']}__run{r['repeat']}.json").write_text(json.dumps(r), encoding="utf-8")
    return d


def test_identical_folders_report_no_change(tmp_path: Path) -> None:
    runs = [_run(repeat=1), _run(repeat=2)]
    b = _folder(tmp_path, "b", runs)
    a = _folder(tmp_path, "a", copy.deepcopy(runs))
    report, changed = cr.compare(cr.load(b), cr.load(a))
    assert changed == 0
    assert "0 change(s)" in report


def test_each_planted_change_is_reported(tmp_path: Path) -> None:
    b = _folder(tmp_path, "b", [_run()])
    after = _run()
    after["overall_status"] = "RED"
    after["alerts"].append({"title": "Creatinine overdue", "evidence": {"type": "rule"}})
    after["plan_items"][0]["model_decision"] = "Gap"
    after["results"][0]["retrieved"][0]["metadata"]["source_path"] = "Data/MarkDown Files/SA.md"
    after["llm_error"] = "timeout"
    a = _folder(tmp_path, "a", [after, _run(pid="P2")])
    report, changed = cr.compare(cr.load(b), cr.load(a))
    for measure in [
        "status",
        "alerts",
        "rule alerts kept on screen",
        "plan items with no model verdict",
        "retrieved passages by document",
        "llm error",
    ]:
        assert f"**{measure}: changed**" in report, measure
    assert "**rule alerts: changed**" not in report
    assert "only in after" in report
    assert "alert titles new: ['Creatinine overdue']" in report
    assert changed == 7


def test_baseline_compared_with_itself_is_unchanged() -> None:
    base = cr.load(ROOT / "eval" / "baseline")
    assert len(base) == 7
    _, changed = cr.compare(base, copy.deepcopy(base))
    assert changed == 0


def test_empty_folder_is_refused(tmp_path: Path) -> None:
    b = _folder(tmp_path, "b", [_run()])
    (tmp_path / "empty").mkdir()
    assert cr.main([str(b), str(tmp_path / "empty")]) == 2
