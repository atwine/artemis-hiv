from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("cac", ROOT / "scripts" / "check_audit_coverage.py")
cac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cac)  # type: ignore[union-attr]

HEAD = subprocess.run(
    ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
).stdout.strip()


def _write(tmp: Path, rows: list, findings_ids: list) -> tuple:
    cov = tmp / "cov.tsv"
    lines = [f"# audited_commit: {HEAD}", "\t".join(cac.COLUMNS)]
    lines += ["\t".join(r) for r in rows]
    cov.write_text("\n".join(lines) + "\n", encoding="utf-8")
    fnd = tmp / "fnd.tsv"
    fnd.write_text("id\tsummary\n" + "".join(f"{i}\tx\n" for i in findings_ids), encoding="utf-8")
    return cov, fnd


def _all_rows(findings: str = "none") -> list:
    return [[f, name, str(line), "s", "reviewer", findings] for f, name, line in cac.functions_at(HEAD)]


def test_complete_coverage_passes(tmp_path: Path) -> None:
    cov, fnd = _write(tmp_path, _all_rows(), [])
    assert cac.check(cov, fnd) == []


def test_missing_function_unread_row_and_unknown_finding_are_reported(tmp_path: Path) -> None:
    rows = _all_rows()
    dropped = rows.pop(0)
    rows[0][4] = ""  # no reader
    rows[1][5] = "F999"  # cites a finding that doesn't exist
    rows.append(["app.py", "made_up", "1", "s", "reviewer", "none"])
    cov, fnd = _write(tmp_path, rows, ["F001"])
    problems = cac.check(cov, fnd)
    assert any(p.startswith("not covered") and dropped[1] in p for p in problems)
    assert any(p.startswith("no reader") for p in problems)
    assert any("unknown finding id F999" in p for p in problems)
    assert any("no such function" in p and "made_up" in p for p in problems)
