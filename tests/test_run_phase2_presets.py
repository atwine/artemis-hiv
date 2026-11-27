"""The runner's GLM presets for the thinking on/off experiment (owner, 2026-11-27)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("run_phase2", ROOT / "scripts" / "run_phase2.py")
run_phase2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_phase2)


def test_the_thinking_preset_is_glm_with_thinking_on_and_its_usage_recorded():
    off, on = run_phase2.PRESETS["glm-5.2"], run_phase2.PRESETS["glm-5.2-thinking"]
    assert on["openrouter"] == off["openrouter"] == "z-ai/glm-5.2"
    assert off["extra"]["reasoning"] == {"enabled": False}
    assert on["extra"] == {"reasoning": {"enabled": True}, "usage": {"include": True}}
