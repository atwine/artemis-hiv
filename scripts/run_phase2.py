"""Run the Phase 2 evaluation cases through the app with one model, saving every run.

    python scripts/run_phase2.py --model llama-a100 --repeats 5
    python scripts/run_phase2.py --model llama-a100 --repeats 5 --temperature 0.2
    python scripts/run_phase2.py --model deepseek-v3.2 --repeats 5 --dry-run

Runs go to eval/phase2/runs/<model>-t<temperature>/<case>__run<k>.json, at the app's default
temperature unless --temperature is given. (Folders without "-t" hold Phase 2's first runs, at
that time's default of 0.2.) Saved runs are skipped, so a stopped run resumes. OpenRouter models
need OPENROUTER_API_KEY in .env; the spend across everything under eval/phase2 is checked before
the run (a worst-case estimate must fit under --cap) and before every check. The A100 model's
address is removed from saved files.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import requests  # noqa: E402
from dotenv import dotenv_values, load_dotenv  # noqa: E402

from artemis.ai.client import (DEFAULT_TEMPERATURE, OpenAICompatClient, OpenAICompatConfig,  # noqa: E402
                               openai_compat_config_from_env)
from artemis import config  # noqa: E402
from artemis.evaluation.cases import NO_KEY, load_cases  # noqa: E402
from artemis.evaluation.scrub import scrub, server_strings  # noqa: E402
from artemis.evaluation.runner import (BudgetExceeded, check_budget, effective_temperature, pending_runs,  # noqa: E402
                                       run_file_name, run_label, spent_in)
from backend.evaluation import RunFailed, run_case  # noqa: E402  (through the backend itself, plan 4C.5)
from backend.patients_db import UnplacedField  # noqa: E402

OPENROUTER = "https://openrouter.ai/api/v1"
# Worst case for one visit check, measured over all 330 Phase 2 checks (2026-11-25): 17,344 tokens
# in, from a model whose plan was cut off and retried; 4,600 out, the app's ceiling (1,600 for the
# alerts plus three plan tries of 1,000).
WORST_IN, WORST_OUT, MARGIN = 17344, 4600, 1.25
PRESETS: Dict[str, Dict[str, Any]] = {
    "llama-a100": {"openrouter": None, "extra": None},
    "deepseek-v3.2": {"openrouter": "deepseek/deepseek-v3.2",
                      "extra": {"reasoning": {"enabled": False}, "usage": {"include": True}}},
    "glm-5.2": {"openrouter": "z-ai/glm-5.2",
                "extra": {"reasoning": {"enabled": False}, "usage": {"include": True}}},
    "claude-haiku-5.5": {"openrouter": "anthropic/claude-haiku-5.5",
                         "extra": {"reasoning": {"enabled": False}, "usage": {"include": True}}},
}
# Left out (measured 2026-11-25): Claude Sonnet 5.5, GLM 5.3 and GLM 5.3 Flash refuse to switch
# thinking off. Sonnet 5.5's thinking filled the app's reply room, so its alert list was cut off.


def _prices(model_id: str) -> tuple:
    data = requests.get(f"{OPENROUTER}/models", timeout=60).json()["data"]
    m = next(x for x in data if x["id"] == model_id)
    return float(m["pricing"]["prompt"]), float(m["pricing"]["completion"])


def model_config(model: str, temperature: Optional[float]) -> Tuple[OpenAICompatConfig, float, float]:
    """The client settings for a preset, and its listed price per token in and out (0 for the A100)."""
    preset = PRESETS[model]
    if preset["openrouter"]:
        key = (dotenv_values(ROOT / ".env").get("OPENROUTER_API_KEY") or "").strip()
        if not key:
            raise SystemExit("OPENROUTER_API_KEY is empty in .env")
        price_in, price_out = _prices(preset["openrouter"])
        return (OpenAICompatConfig(base_url=OPENROUTER, model=preset["openrouter"], api_key=key,
                                   temperature=temperature, extra_body=preset["extra"]), price_in, price_out)
    env = openai_compat_config_from_env()
    if env is None:
        raise SystemExit("LLM_BASE_URL is not set in .env")
    return dataclasses.replace(env, temperature=temperature), 0.0, 0.0


def _write(path: Path, record: Dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True, choices=sorted(PRESETS))
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--temperature", type=float, default=None, help=f"default: the app's own ({DEFAULT_TEMPERATURE:g})")
    ap.add_argument("--variant", default="", help="names the setup under test (Phase 2B), so its runs get their own folder")
    ap.add_argument("--cap", type=float, default=5.0, help="dollars, across everything under eval/phase2")
    ap.add_argument("--cases", type=Path, default=ROOT / "eval" / "cases")
    ap.add_argument("--root", type=Path, default=ROOT / "eval" / "phase2")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    temperature = effective_temperature(args.temperature)
    label = run_label(args.model, temperature, args.variant)
    out = args.root / "runs" / label
    cases = load_cases(args.cases)
    if any(c.key_status == NO_KEY for c in cases):
        raise SystemExit("every case needs its answer key before a run")
    todo = list(pending_runs(out, cases, args.repeats))

    settings, price_in, price_out = model_config(args.model, temperature)
    per_check = (WORST_IN * price_in + WORST_OUT * price_out) * MARGIN
    spent = spent_in(args.root)
    print(f"{label}: {len(todo)} checks to run; worst case ${per_check:.4f} each, "
          f"${len(todo) * per_check:.2f} in all; ${spent:.4f} spent so far; cap ${args.cap:.2f}")
    try:
        check_budget(spent=spent, checks=len(todo), per_check=per_check, cap=args.cap)
    except BudgetExceeded as exc:
        raise SystemExit(f"refused: {exc}")
    if args.dry_run or not todo:
        return 0

    out.mkdir(parents=True, exist_ok=True)
    load_dotenv(ROOT / ".env", override=False)  # the search model's folder (ARTEMIS_MODEL_DIR)
    rag = config.guideline_search()
    if config.GUIDELINE_PATHS:
        rag.ensure_indexed()
    client = OpenAICompatClient(settings)
    secrets = server_strings()
    for case, k in todo:
        try:
            check_budget(spent=spent, checks=1, per_check=per_check, cap=args.cap)
        except BudgetExceeded:
            print(f"stopped before {case.case_id} #{k}: one more check could pass the ${args.cap:.2f} cap")
            return 1
        try:
            record = scrub(run_case(case, client, rag, label=label, repeat=k, price_in=price_in,
                                    price_out=price_out, temperature=temperature), secrets)
        except (RunFailed, UnplacedField) as exc:
            # Not saved, so its cost isn't counted against the cap: say what it was.
            cost = getattr(exc, "cost_usd", 0.0)
            print(f"stopped at {case.case_id} #{k}: the backend refused it ({scrub(str(exc), secrets)[:300]}); "
                  f"nothing saved for it; ${cost:.4f} spent on it, not counted in the saved runs")
            return 2
        if record["screening_outcome"] == "failed":  # the model server did not answer
            # Not saved: a server outage is not a result, and a saved run would be skipped on resume.
            print(f"stopped at {case.case_id} #{k}: the model server did not answer; nothing saved for it")
            return 2
        _write(out / run_file_name(case.case_id, k), record)
        spent += record["cost_usd"]
        print(f"  {case.case_id} #{k}: {record['status']}, {len(record['alerts'])} alerts, "
              f"{record['seconds']} s, ${record['cost_usd']:.4f} (total ${spent:.4f})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
