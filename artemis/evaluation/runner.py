"""Running the app on evaluation cases with a chosen model, and guarding the spend (Phase 2).

Each run is one visit check through the app's own analysis (rules, AI review, plan step), saved
as one JSON record per case and repeat. Records already saved are skipped, so a stopped run
picks up where it left off. The spend is checked before a run starts (a worst-case estimate
must fit under the cap) and after every check.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from artemis.evaluation.cases import Case, case_file_name
from artemis.visit import AnalysisOptions, run_visit_analysis


class BudgetExceeded(RuntimeError):
    """A run that could take the spend past the cap."""


class MeteredClient:
    """Wraps a model client and keeps the usage the server reported for each call."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.usages: List[Optional[Dict[str, Any]]] = []

    def chat(self, *args: Any, **kwargs: Any) -> Optional[str]:
        reply = self._client.chat(*args, **kwargs)
        self.usages.append(getattr(self._client, "last_usage", None))
        return reply

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def cost_of(usages: List[Optional[Dict[str, Any]]], price_in: float, price_out: float) -> float:
    """Dollars for a list of calls: the server's own figure, or tokens times the listed price."""
    total = 0.0
    for u in usages:
        if not u:
            continue
        if u.get("cost") is not None:
            total += float(u["cost"])
        else:
            total += float(u.get("prompt_tokens") or 0) * price_in + float(u.get("completion_tokens") or 0) * price_out
    return total


def spent_in(folder: Path) -> float:
    """Dollars recorded under a folder: each saved case run (.json) and each quiz answer (.jsonl line).

    A record that can't be read stops the count: counting it as $0 could let a run pass the cap.
    The one exception is a quiz file's last line, which a crash can cut off mid-write.
    """
    total = 0.0
    for f in Path(folder).rglob("*.json*"):
        if f.suffix not in (".json", ".jsonl"):
            continue
        lines = f.read_text(encoding="utf-8").splitlines() if f.suffix == ".jsonl" else [f.read_text(encoding="utf-8")]
        for i, line in enumerate(lines):
            try:
                total += float(json.loads(line).get("cost_usd") or 0)
            except (ValueError, AttributeError) as exc:
                if f.suffix == ".jsonl" and i == len(lines) - 1:
                    continue
                raise ValueError(f"can't read the cost in {f} (line {i + 1})") from exc
    return total


def check_budget(*, spent: float, checks: int, per_check: float, cap: float) -> None:
    if spent + checks * per_check > cap:
        raise BudgetExceeded(
            f"${spent:.2f} spent + {checks} checks x ${per_check:.4f} (worst case) = "
            f"${spent + checks * per_check:.2f}, over the ${cap:.2f} cap"
        )


def run_file_name(case_id: str, repeat: int) -> str:
    return case_file_name(case_id).replace(".json", f"__run{repeat}.json")


def pending_runs(folder: Path, cases: List[Case], repeats: int) -> Iterator[Tuple[Case, int]]:
    for case in cases:
        for k in range(1, repeats + 1):
            if not (Path(folder) / run_file_name(case.case_id, k)).exists():
                yield case, k


def run_case(case: Case, client: Any, rag: Any, *, label: str, repeat: int, price_in: float = 0.0,
             price_out: float = 0.0, temperature: Optional[float] = None) -> Dict[str, Any]:
    """One visit check of the case through the app's analysis, as a JSON-ready record."""
    metered = MeteredClient(client)
    note = (case.patient.get("today_encounter") or {}).get("note") or ""
    t0 = time.perf_counter()
    result = run_visit_analysis(
        patient=case.patient, today_note=note, rag=rag, llm_client=metered,
        options=AnalysisOptions(top_k=5, use_llm=True, agentic=True),
    )
    seconds = time.perf_counter() - t0
    plan = result.agentic_result
    record = {
        "case_id": case.case_id,
        "model": label,
        "model_id": getattr(client, "model", None),
        "repeat": repeat,
        "temperature": temperature,
        "seconds": round(seconds, 1),
        "calls": metered.usages,
        "cost_usd": cost_of(metered.usages, price_in, price_out),
        "status": result.status,
        "screening_outcome": result.screening_outcome,
        "llm_error": result.llm_error,
        "alerts": [asdict(a) for a in result.alerts],
        "retrieved": {r["alert"].alert_id: [c.chunk_id for c in r["retrieved"]] for r in result.results},
        "screening": result.screening_debug,
        "plan_text": getattr(plan, "updated_management_plan_text", None),
        "plan_issues": list(getattr(plan, "plan_issues", []) or []),
    }
    return json.loads(json.dumps(record, default=str))
