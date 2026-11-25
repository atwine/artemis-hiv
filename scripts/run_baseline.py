"""Run every test patient through the app's own analysis and save what comes out.

Plan item 1.0. This calls app._run_analysis, the function behind the "Save encounter"
button, with the app's default settings, so a rerun after a fix shows that fix's effect.
Streamlit is swapped for a small stand-in that keeps session state in a dict.

    python scripts/run_baseline.py                      # all patients, 3 repeats, eval/baseline/
    python scripts/run_baseline.py --out eval/after-1.1
    python scripts/run_baseline.py --patients P001 --repeats 1

Each patient gets one JSON file per repeat, written to a temporary name and then renamed,
so an interrupted run never leaves a half-written file. Rerunning skips files that exist
unless --force is given. summary.md is rebuilt from the saved files at the end.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as _streamlit  # noqa: E402

import app  # noqa: E402  (loads .env and the app's settings)
from modules.llm_client import openai_compat_config_from_env  # noqa: E402

# The app's defaults (app.py "Advanced settings" and "LLM settings"), with one exception:
# the agentic ARTEMIS plan checkbox starts unticked in the app. It is on here because
# fix 1.2 is about that plan.
SETTINGS: Dict[str, Any] = {
    "prefer_chroma": True,
    "embedding_model_name": "all-MiniLM-L6-v2",
    "top_k": 5,
    "index_max_pages": None,
    "retrieval_page_range": None,
    "use_ollama": True,
    "llm_mode": "LLM screening (generate alerts)",
    "ollama_model": None,
    "ollama_num_ctx": 8192,
    "show_llm_narrative": False,
    "agentic_review": True,
}


class _Status:
    """Stand-in for st.status: records each label instead of drawing it."""

    def __init__(self, log: List[str], label: str) -> None:
        self._log = log
        self._log.append(label)

    def update(self, label: str = "", state: str = "", **_: Any) -> None:
        self._log.append(f"{state}: {label}" if state else label)


class _StreamlitShim:
    """Everything the analysis touches on `st`, minus the screen."""

    def __init__(self) -> None:
        self.session_state: Dict[str, Any] = {}
        self.status_log: List[str] = []

    def status(self, label: str, **_: Any) -> _Status:
        return _Status(self.status_log, label)

    def __getattr__(self, name: str) -> Any:
        # cache_resource and friends work without a running Streamlit server.
        return getattr(_streamlit, name)


def _load_patients() -> List[Dict[str, Any]]:
    patients: List[Dict[str, Any]] = []
    for path in (app.MOCK_PATIENTS_PATH, app.CUSTOM_PATIENTS_PATH):
        if path.exists():
            patients.extend(json.loads(path.read_text(encoding="utf-8")))
    return patients


def _safe_name(patient_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", patient_id).strip("_")


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return _to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


_ROOT_PREFIXES = sorted(
    {str(PROJECT_ROOT) + os.sep, PROJECT_ROOT.as_posix() + "/"}, key=len, reverse=True
)


def _scrub(obj: Any, secrets: List[str]) -> Any:
    """Keep the model server's address and local folder paths out of saved files (the repo is public)."""
    if isinstance(obj, str):
        for s in secrets:
            obj = obj.replace(s, "<model-server>")
        for prefix in _ROOT_PREFIXES:
            obj = obj.replace(prefix, "")
        return obj
    if isinstance(obj, dict):
        return {k: _scrub(v, secrets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub(v, secrets) for v in obj]
    return obj


def _server_strings() -> List[str]:
    cfg = openai_compat_config_from_env()
    if cfg is None:
        return []
    base = cfg.base_url.rstrip("/")
    host = re.sub(r"^https?://", "", base).split("/")[0]
    return sorted({base, host, host.split(":")[0]}, key=len, reverse=True)


def _plan_items(agentic: Any) -> List[Dict[str, Any]]:
    """The plan's problems with the model's own verdict on each, as returned.

    Stricter than the screen, which also repairs small JSON slips before rendering, so a
    plan the screen can show may come back here as {"parse_error": True}.
    """
    text = getattr(agentic, "updated_management_plan_text", None) if agentic is not None else None
    if not text:
        return []
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        obj = json.loads(text[start:end])
    except ValueError:
        return [{"parse_error": True}]
    items = []
    for p in obj.get("problems") or []:
        if isinstance(p, dict):
            cp = p.get("clinician_plan_for_this_problem") or {}
            items.append(
                {
                    "action": p.get("action"),
                    "reason": p.get("reason"),
                    "model_decision": cp.get("decision") if isinstance(cp, dict) else None,
                }
            )
    return items


def run_one(patient: Dict[str, Any]) -> Dict[str, Any]:
    shim = _StreamlitShim()
    shim.session_state["agentic_ui_debug_enabled"] = SETTINGS["agentic_review"]
    app.st = shim  # the analysis reads and writes `st` as a module global

    kwargs = {k: v for k, v in SETTINGS.items() if k != "agentic_review"}
    note = (patient.get("today_encounter") or {}).get("note") or ""
    t0 = time.perf_counter()
    app._run_analysis(patient=patient, today_note=note, **kwargs)
    seconds = time.perf_counter() - t0

    ss = shim.session_state
    agentic = ss.get("agentic_debug_result")
    # What the fixed rules raise on their own. The app drops these when LLM screening
    # succeeds (plan item 1.1), so record them separately.
    rule_patient = copy.deepcopy(patient)
    rule_patient.setdefault("today_encounter", {})["note"] = note
    rule_alerts = app.run_alerts(app.build_patient_context(rule_patient))
    results = []
    for r in ss.get("analysis_results") or []:
        expl = r.get("explanation")
        results.append(
            {
                "alert_id": r["alert"].alert_id,
                "explanation": getattr(expl, "text", None),
                "explanation_used_llm": getattr(expl, "used_llm", None),
                "retrieved": [
                    {
                        "chunk_id": c.chunk_id,
                        "distance": c.distance,
                        "metadata": c.metadata,
                        "excerpt": (c.document or "")[:400],
                    }
                    for c in (r.get("retrieved") or [])
                ],
            }
        )
    return {
        "patient_id": patient.get("patient_id"),
        "git_commit": _git_commit(),
        "model": getattr(openai_compat_config_from_env(), "model", None),
        "seconds": round(seconds, 1),
        "overall_status": ss.get("analysis_status"),
        "llm_error": ss.get("analysis_ollama_error"),
        "expected_demo_outcome": patient.get("expected_demo_outcome"),
        "rule_alerts": _to_jsonable(rule_alerts),
        "alerts": _to_jsonable(ss.get("analysis_alerts") or []),
        "results": _to_jsonable(results),
        "screening": _to_jsonable(ss.get("analysis_screening_debug")),
        "patient_facts_seen": _to_jsonable(ss.get("analysis_screening_patient_facts")),
        "plan_items": _plan_items(agentic),
        "agentic_result": _to_jsonable(agentic),
        "status_log": shim.status_log,
    }


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True
        )
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        ).stdout.strip()
        return out.stdout.strip() + ("+uncommitted" if dirty else "")
    except OSError:
        return "unknown"


def _write_json(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_summary(out_dir: Path) -> None:
    runs: Dict[str, List[Dict[str, Any]]] = {}
    for f in sorted(out_dir.glob("*__run*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        runs.setdefault(d["patient_id"], []).append(d)

    lines = [
        "# Baseline summary",
        "",
        "Generated by `scripts/run_baseline.py` from the JSON files in this folder.",
        "",
        "| Patient | Runs | Status per run | Alerts per run | Rule alerts (dropped) | Plan items per run | Items with no model verdict | Seconds (median, range) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for pid, rs in runs.items():
        secs = sorted(r["seconds"] for r in rs)
        no_verdict = [sum(1 for i in r["plan_items"] if not i.get("model_decision")) for r in rs]
        lines.append(
            f"| {pid} | {len(rs)} | {', '.join(str(r['overall_status']) for r in rs)} "
            f"| {', '.join(str(len(r['alerts'])) for r in rs)} "
            f"| {len(rs[0].get('rule_alerts') or [])} "
            f"| {', '.join(str(len(r['plan_items'])) for r in rs)} "
            f"| {', '.join(map(str, no_verdict))} | {statistics.median(secs)} ({secs[0]} to {secs[-1]}) |"
        )
    lines += ["", "## Alert titles per run", ""]
    for pid, rs in runs.items():
        lines.append(f"### {pid}")
        if rs[0].get("expected_demo_outcome"):
            lines.append(f"- Expected (from the test data): {json.dumps(rs[0]['expected_demo_outcome'], ensure_ascii=False)}")
        rule_titles = "; ".join(a.get("title", "") for a in rs[0].get("rule_alerts") or []) or "(none)"
        lines.append(f"- Fixed rules alone: {rule_titles}")
        for i, r in enumerate(rs, 1):
            titles = "; ".join(a.get("title", "") for a in r["alerts"]) or "(none)"
            err = f" LLM error: {r['llm_error']}" if r.get("llm_error") else ""
            lines.append(f"- Run {i}: {titles}{err}")
        lines.append("")
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="eval/baseline", help="output folder (default eval/baseline)")
    ap.add_argument("--patients", nargs="*", help="patient ids to run (default: all)")
    ap.add_argument("--repeats", type=int, default=3, help="runs per patient (default 3)")
    ap.add_argument("--force", action="store_true", help="redo runs whose file already exists")
    args = ap.parse_args(argv)

    if openai_compat_config_from_env() is None:
        print("LLM_BASE_URL is not set in .env; refusing to run against a fallback model.")
        return 2

    out_dir = (PROJECT_ROOT / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    secrets = _server_strings()

    patients = _load_patients()
    if args.patients:
        wanted = set(args.patients)
        patients = [p for p in patients if p.get("patient_id") in wanted]
    if not patients:
        print("No matching patients.")
        return 2

    # run.json describes the folder's first full run; each run file also records its own
    # commit and model, so a partial rerun never misdescribes files it skipped.
    cfg = openai_compat_config_from_env()
    if args.force or not (out_dir / "run.json").exists():
        _write_json(
            out_dir / "run.json",
            {
                "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "git_commit": _git_commit(),
                "model": cfg.model if cfg else None,
                "settings": SETTINGS,
                "patients": [p.get("patient_id") for p in patients],
                "repeats": args.repeats,
            },
        )

    for p in patients:
        pid = str(p.get("patient_id"))
        for k in range(1, args.repeats + 1):
            path = out_dir / f"{_safe_name(pid)}__run{k}.json"
            if path.exists() and not args.force:
                print(f"skip {path.name} (exists)")
                continue
            print(f"run  {pid} #{k} ...", flush=True)
            data = _scrub(run_one(p), secrets)
            data["repeat"] = k
            _write_json(path, data)
            print(f"     {data['overall_status']}, {len(data['alerts'])} alerts, {data['seconds']} s", flush=True)

    write_summary(out_dir)
    print(f"summary: {out_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
