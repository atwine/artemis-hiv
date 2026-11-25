"""Check that the Phase 1 audit read every function on the analysis path.

The coverage file (docs/audit/phase1-coverage.tsv) has one row per function in app.py and
modules/*.py, as they were at the audited commit named on its first line:

    # audited_commit: <sha>
    file<TAB>function<TAB>line<TAB>slice<TAB>read_by<TAB>findings

`findings` is a comma-separated list of finding ids from docs/audit/phase1-findings.tsv,
or "none". The check fails if any function at that commit is missing, if a row names a
function that doesn't exist there, if a row has no reader or no findings entry, or if a
row cites a finding id the findings file doesn't have.

    python scripts/check_audit_coverage.py              # check
    python scripts/check_audit_coverage.py --skeleton   # print empty rows for HEAD
"""

from __future__ import annotations

import argparse
import ast
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "docs" / "audit" / "phase1-coverage.tsv"
FINDINGS = ROOT / "docs" / "audit" / "phase1-findings.tsv"
COLUMNS = ["file", "function", "line", "slice", "read_by", "findings"]

Key = Tuple[str, str, int]  # file, qualified function name, line


def _source_files(commit: str) -> List[str]:
    out = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", commit, "--", "app.py", "modules"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    return sorted(f for f in out if f.endswith(".py"))


def _functions(source: str) -> List[Tuple[str, int]]:
    found: List[Tuple[str, int]] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                found.append((name, child.lineno))
                walk(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            else:
                walk(child, prefix)

    walk(ast.parse(source), "")
    return found


def functions_at(commit: str) -> List[Key]:
    keys: List[Key] = []
    for f in _source_files(commit):
        src = subprocess.run(
            ["git", "show", f"{commit}:{f}"], cwd=ROOT, capture_output=True, text=True,
            check=True, encoding="utf-8",
        ).stdout
        keys.extend((f, name, line) for name, line in _functions(src))
    return keys


def _read_coverage(path: Path) -> Tuple[Optional[str], List[Dict[str, str]]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    commit = None
    if lines and lines[0].startswith("# audited_commit:"):
        commit = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]
    return commit, list(csv.DictReader(lines, delimiter="\t"))


def _finding_ids(path: Path) -> set:
    if not path.exists():
        return set()
    rows = csv.DictReader(path.read_text(encoding="utf-8").splitlines(), delimiter="\t")
    return {r["id"].strip() for r in rows if r.get("id")}


def check(coverage: Path = COVERAGE, findings: Path = FINDINGS) -> List[str]:
    problems: List[str] = []
    if not coverage.exists():
        return [f"{coverage} does not exist"]
    commit, rows = _read_coverage(coverage)
    if not commit:
        return ["first line must be '# audited_commit: <sha>'"]
    expected = set(functions_at(commit))
    seen: Dict[Key, Dict[str, str]] = {}
    for r in rows:
        try:
            key = (r["file"], r["function"], int(r["line"]))
        except (KeyError, TypeError, ValueError):
            problems.append(f"malformed row: {r}")
            continue
        if key in seen:
            problems.append(f"duplicate row: {key}")
        seen[key] = r
    for key in sorted(expected - set(seen)):
        problems.append(f"not covered: {key[0]}:{key[2]} {key[1]}")
    for key in sorted(set(seen) - expected):
        problems.append(f"no such function at {commit}: {key[0]}:{key[2]} {key[1]}")
    ids = _finding_ids(findings)
    for key, r in sorted(seen.items()):
        if key not in expected:
            continue
        if not (r.get("read_by") or "").strip():
            problems.append(f"no reader: {key[0]}:{key[2]} {key[1]}")
        cited = (r.get("findings") or "").strip()
        if not cited:
            problems.append(f"no findings entry (use 'none'): {key[0]}:{key[2]} {key[1]}")
        elif cited != "none":
            for fid in (x.strip() for x in cited.split(",")):
                if fid not in ids:
                    problems.append(f"unknown finding id {fid}: {key[0]}:{key[2]} {key[1]}")
    return problems


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--skeleton", action="store_true", help="print empty rows for HEAD")
    args = ap.parse_args(argv)
    if args.skeleton:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        print(f"# audited_commit: {head}")
        print("\t".join(COLUMNS))
        for f, name, line in functions_at(head):
            print("\t".join([f, name, str(line), "", "", ""]))
        return 0
    problems = check()
    for p in problems:
        print(p)
    commit, rows = _read_coverage(COVERAGE) if COVERAGE.exists() else (None, [])
    print(f"{len(problems)} problem(s); {len(rows)} rows; audited commit {commit}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
