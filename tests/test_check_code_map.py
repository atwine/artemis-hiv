from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ccm", ROOT / "scripts" / "check_code_map.py")
ccm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccm)  # type: ignore[union-attr]


def _project(tmp: Path) -> Path:
    (tmp / "modules").mkdir()
    (tmp / "ui").mkdir()
    (tmp / "app.py").write_text("def main():\n    def helper():\n        pass\n", encoding="utf-8")
    (tmp / "modules" / "rules.py").write_text("def check():\n    pass\n", encoding="utf-8")
    (tmp / "ui" / "state.py").write_text("def clear():\n    pass\n", encoding="utf-8")
    return tmp


def _write(path: Path, header: list, rows: list) -> Path:
    path.write_text("\t".join(header) + "\n" + "".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
    return path


FULL_MAP = [
    ["app.py", "main", "Draws the screen.", "ui/", "to-move"],
    ["app.py", "main.helper", "Helps.", "ui/", "to-move"],
    ["modules/rules.py", "check", "Runs the rules.", "artemis/rules/", "to-move"],
    ["ui/state.py", "clear", "Forgets the last result.", "ui/state.py", "stays"],
]


def test_a_complete_map_and_a_true_moves_log_pass(tmp_path: Path) -> None:
    root = _project(tmp_path)
    cmap = _write(root / "map.tsv", ccm.MAP_COLUMNS, FULL_MAP)
    moves = _write(
        root / "moves.tsv",
        ccm.MOVE_COLUMNS,
        [
            ["2026-11-25", "fix 2", "move", "app.py:old_clear", "ui/state.py:clear", "test_x"],
            ["2026-11-25", "fix 1", "delete", "app.py:dead", "-", "grep: no callers"],
        ],
    )
    assert ccm.check(cmap, moves, root) == []


def test_each_planted_mistake_is_reported(tmp_path: Path) -> None:
    root = _project(tmp_path)
    rows = [r[:] for r in FULL_MAP[1:]]  # main is not mapped
    rows[0][2] = ""  # no description
    rows.append(["app.py", "gone", "Was here.", "ui/", "to-move"])  # no such function
    rows[1][4] = "maybe"  # unknown status
    cmap = _write(root / "map.tsv", ccm.MAP_COLUMNS, rows)
    moves = _write(
        root / "moves.tsv",
        ccm.MOVE_COLUMNS,
        [
            ["2026-11-25", "fix 2", "move", "modules/rules.py:check", "artemis/rules/x.py:check", "t"],
            ["2026-11-25", "fix 2", "delete", "ui/state.py:clear", "-", ""],
        ],
    )
    problems = ccm.check(cmap, moves, root)
    joined = "\n".join(problems)
    assert "map: not mapped app.py:main" in joined
    assert "map: empty 'does' for app.py:main.helper" in joined
    assert "map: no such function app.py:gone" in joined
    assert "unknown status 'maybe'" in joined
    assert "modules/rules.py:check was moved but still exists" in joined
    assert "new home artemis/rules/x.py:check does not exist" in joined
    assert "ui/state.py:clear was deleted but still exists" in joined
    assert "empty 'proof'" in joined


def test_the_real_code_map_and_moves_log_match_the_code() -> None:
    # Every function is mapped, every recorded move really happened. See docs/refactor/README.md.
    assert ccm.check() == []
