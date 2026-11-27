"""Running the app on evaluation cases with a chosen model, and guarding the spend (Phase 2).

Each run is one visit through the backend itself (backend/evaluation.py run_case, plan 4C.5): the
check, then its plan, saved as one JSON record per case and repeat. Records already saved are
skipped, so a stopped run picks up where it left off. The spend is checked before a run starts (a worst-case estimate
must fit under the cap) and after every check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from artemis.ai.client import DEFAULT_TEMPERATURE
from artemis.evaluation.cases import Case, case_file_name


class BudgetExceeded(RuntimeError):
    """A run that could take the spend past the cap."""


class MeteredClient:
    """Wraps a model client and keeps the usage the server reported for each call."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.usages: List[Optional[Dict[str, Any]]] = []

    def chat(self, *args: Any, **kwargs: Any) -> Any:
        reply = self._client.chat(*args, **kwargs)
        self.usages.append(reply.usage)
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


def effective_temperature(temperature: Optional[float]) -> float:
    """The temperature a run really uses: the one asked for, or the app's default."""
    return DEFAULT_TEMPERATURE if temperature is None else float(temperature)


def run_label(model: str, temperature: Optional[float], variant: str = "") -> str:
    """A run's folder name. It always names the temperature used, and the setup under test when
    there is one (a Phase 2B change): saved runs are skipped on resume, so runs at different
    temperatures or setups must never share a folder. (Phase 2's first runs, in folders without
    "-t", used the default of that time, 0.2.)"""
    return f"{model}-t{effective_temperature(temperature):g}" + (f"-{variant}" if variant else "")


def run_file_name(case_id: str, repeat: int) -> str:
    return case_file_name(case_id).replace(".json", f"__run{repeat}.json")


def pending_runs(folder: Path, cases: List[Case], repeats: int) -> Iterator[Tuple[Case, int]]:
    for case in cases:
        for k in range(1, repeats + 1):
            if not (Path(folder) / run_file_name(case.case_id, k)).exists():
                yield case, k
