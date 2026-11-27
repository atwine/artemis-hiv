"""scripts/run_phase2.py end to end, with a stand-in model and search: nothing is sent or spent.

Added 2026-11-27 after review: plan 4C.1 gave the guideline-search module the name `config`,
which main() also uses for the model settings, so every real run crashed before its first check.
Importing the script (tests/test_no_streamlit.py) couldn't catch that (lesson 23:
scripts nobody runs break quietly).
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_a_run_goes_through_every_case_and_saves_it(tmp_path, monkeypatch):
    from artemis import config
    from artemis.ai.client import OpenAICompatConfig
    from artemis.evaluation.cases import load_cases
    from tests.api_fakes import FakeModel, fake_search, replies_for

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    run_phase2 = importlib.import_module("run_phase2")
    settings = OpenAICompatConfig(base_url="http://model.invalid/v1", model="stand-in")
    monkeypatch.setattr(run_phase2, "model_config", lambda model, temperature: (settings, 0.0, 0.0))
    monkeypatch.setattr(run_phase2, "OpenAICompatClient", lambda cfg: FakeModel(replies_for("P001")))
    monkeypatch.setattr(run_phase2, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(run_phase2, "server_strings", lambda: [])
    monkeypatch.setattr(config, "guideline_search", lambda *a, **k: fake_search())

    code = run_phase2.main(["--model", "llama-a100", "--repeats", "1", "--root", str(tmp_path)])

    assert code == 0
    saved = sorted((tmp_path / "runs").rglob("*.json"))
    cases = {c.case_id for c in load_cases(ROOT / "eval" / "cases")}
    assert len(saved) == len(cases)
    assert {json.loads(p.read_text(encoding="utf-8"))["case_id"] for p in saved} == cases
    sys.modules.pop("run_phase2", None)


def test_a_model_server_that_does_not_answer_stops_the_run_and_saves_nothing(tmp_path, monkeypatch):
    """A server outage is not a result: nothing is saved, so a resumed run does the case again.
    Since 4C.5 the record says so in screening_outcome ("failed": the server did not answer)."""
    from artemis import config
    from artemis.ai.client import OpenAICompatConfig
    from tests.api_fakes import FakeModel, fake_search

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    run_phase2 = importlib.import_module("run_phase2")
    settings = OpenAICompatConfig(base_url="http://model.invalid/v1", model="stand-in")
    monkeypatch.setattr(run_phase2, "model_config", lambda model, temperature: (settings, 0.0, 0.0))
    monkeypatch.setattr(run_phase2, "OpenAICompatClient", lambda cfg: FakeModel({}, fail=True))
    monkeypatch.setattr(run_phase2, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(run_phase2, "server_strings", lambda: [])
    monkeypatch.setattr(config, "guideline_search", lambda *a, **k: fake_search())

    code = run_phase2.main(["--model", "llama-a100", "--repeats", "1", "--root", str(tmp_path)])

    assert code == 2
    assert sorted((tmp_path / "runs").rglob("*.json")) == []


def test_a_case_the_backend_refuses_stops_the_run_and_says_what_it_cost(tmp_path, monkeypatch, capsys):
    """Code review, 2026-11-27: a case the backend refuses (here a note over the visit check's limit)
    stopped the run with a traceback. It stops cleanly now, saves nothing for that case, and says
    what was spent on it, since a cost that isn't saved isn't counted against the cap."""
    import shutil

    from artemis import config
    from artemis.ai.client import OpenAICompatConfig
    from tests.api_fakes import FakeModel, fake_search, replies_for

    cases = tmp_path / "cases"
    cases.mkdir()
    shutil.copy(ROOT / "eval" / "cases" / "P001.json", cases / "P001.json")
    case = json.loads((cases / "P001.json").read_text(encoding="utf-8"))
    case["patient"]["today_encounter"]["note"] = "x" * 20001
    (cases / "P001.json").write_text(json.dumps(case), encoding="utf-8")

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    run_phase2 = importlib.import_module("run_phase2")
    settings = OpenAICompatConfig(base_url="http://model.invalid/v1", model="stand-in")
    monkeypatch.setattr(run_phase2, "model_config", lambda model, temperature: (settings, 0.0, 0.0))
    monkeypatch.setattr(run_phase2, "OpenAICompatClient", lambda cfg: FakeModel(replies_for("P001")))
    monkeypatch.setattr(run_phase2, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(run_phase2, "server_strings", lambda: [])
    monkeypatch.setattr(config, "guideline_search", lambda *a, **k: fake_search())

    code = run_phase2.main(["--model", "llama-a100", "--repeats", "1", "--root", str(tmp_path / "out"),
                            "--cases", str(cases)])

    assert code == 2
    assert sorted((tmp_path / "out").rglob("*.json")) == []
    out = capsys.readouterr().out
    assert "stopped at P001 #1" in out and "422" in out and "$0.0000" in out
