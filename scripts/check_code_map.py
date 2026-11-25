"""Check that the code map and the moves log match the code on disk.

docs/refactor/code-map.tsv has one row per function in app.py, modules/, ui/ and artemis/:

    file  function  does  target  status

- `does`: what it does, in plain words.
- `target`: where it belongs in the new layout (a folder or file), or `stays`.
- `status`: `stays` (already in its final place), `to-move` (still at `file`, going to
  `target`) or `moved` (moved here in the restructure; `target` repeats `file`).

docs/refactor/moves.tsv has one row per move or deletion:

    date  fix  what  from  to  proof

- `what`: `move`, `delete` or `rewrite`.
- `from` / `to`: `file:function`. `to` is `-` for a delete.
- `proof`: the check that showed nothing broke (a test name, the golden check, a grep
  showing no callers).

The check fails when a function in the code has no map row, a map row names a function that
doesn't exist, a row has an empty field or an unknown status, a move's old copy still exists,
a move's new home doesn't exist, or a row has no proof.

    python scripts/check_code_map.py             # check
    python scripts/check_code_map.py --missing   # print map rows to add for unmapped functions
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
CODE_MAP = ROOT / "docs" / "refactor" / "code-map.tsv"
MOVES = ROOT / "docs" / "refactor" / "moves.tsv"
MAP_COLUMNS = ["file", "function", "does", "target", "status"]
MOVE_COLUMNS = ["date", "fix", "what", "from", "to", "proof"]  # plus an optional "note" column
STATUSES = {"stays", "to-move", "moved"}
WHATS = {"move", "delete", "rewrite"}


def code_files(root: Path = ROOT) -> List[str]:
    files = ["app.py"] if (root / "app.py").exists() else []
    for folder in ("modules", "ui", "artemis"):
        files += sorted(p.relative_to(root).as_posix() for p in (root / folder).rglob("*.py"))
    return files


def functions_in(source: str) -> List[str]:
    found: List[str] = []

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                found.append(name)
                walk(child, f"{name}.")
            elif isinstance(child, ast.ClassDef):
                walk(child, f"{prefix}{child.name}.")
            else:
                walk(child, prefix)

    walk(ast.parse(source), "")
    return found


def functions_on_disk(root: Path = ROOT) -> Set[Tuple[str, str]]:
    out: Set[Tuple[str, str]] = set()
    for f in code_files(root):
        for name in functions_in((root / f).read_text(encoding="utf-8")):
            out.add((f, name))
    return out


def _rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.startswith("#")]
    return [{k: (v or "").strip() for k, v in r.items()} for r in csv.DictReader(lines, delimiter="\t")]


def _split_ref(ref: str) -> Tuple[str, str]:
    file, _, func = ref.partition(":")
    return file.strip(), func.strip()


def check(code_map: Path = CODE_MAP, moves: Path = MOVES, root: Path = ROOT) -> List[str]:
    problems: List[str] = []
    on_disk = functions_on_disk(root)
    mapped: Dict[Tuple[str, str], Dict[str, str]] = {}
    for r in _rows(code_map):
        key = (r.get("file", ""), r.get("function", ""))
        if key in mapped:
            problems.append(f"map: duplicate row {key[0]}:{key[1]}")
        mapped[key] = r
        for col in MAP_COLUMNS:
            if not r.get(col):
                problems.append(f"map: empty '{col}' for {key[0]}:{key[1]}")
        if r.get("status") and r["status"] not in STATUSES:
            problems.append(f"map: unknown status '{r['status']}' for {key[0]}:{key[1]}")
    for key in sorted(on_disk - set(mapped)):
        problems.append(f"map: not mapped {key[0]}:{key[1]}")
    for key in sorted(set(mapped) - on_disk):
        problems.append(f"map: no such function {key[0]}:{key[1]}")

    move_rows = _rows(moves)
    # A function can move or be replaced more than once (a -> b, later b -> c). A row's new home is valid
    # when the chain of later moves ends at a function that exists.
    later_moves: Dict[Tuple[str, str], Tuple[str, str]] = {}
    deleted_later: Set[Tuple[str, str]] = set()
    for r in move_rows:
        if r.get("what") in {"move", "rewrite"}:
            later_moves[_split_ref(r.get("from", ""))] = _split_ref(r.get("to", ""))
        elif r.get("what") == "delete":
            deleted_later.add(_split_ref(r.get("from", "")))

    def final_home(ref: Tuple[str, str]) -> Tuple[str, str]:
        seen = set()
        while ref not in on_disk and ref in later_moves and ref not in seen:
            seen.add(ref)
            ref = later_moves[ref]
        return ref

    for i, r in enumerate(move_rows, start=2):
        where = f"moves line {i}"
        for col in MOVE_COLUMNS:
            if not r.get(col):
                problems.append(f"{where}: empty '{col}'")
        what = r.get("what", "")
        if what and what not in WHATS:
            problems.append(f"{where}: unknown what '{what}'")
        src, dst = _split_ref(r.get("from", "")), _split_ref(r.get("to", ""))
        if what in {"move", "delete"} and src in on_disk:
            problems.append(f"{where}: {src[0]}:{src[1]} was {what}d but still exists")
        home = final_home(dst)
        if what in {"move", "rewrite"} and home not in on_disk and home not in deleted_later:
            problems.append(f"{where}: new home {dst[0]}:{dst[1]} does not exist")
    return problems


def missing_rows(code_map: Path = CODE_MAP, root: Path = ROOT) -> List[str]:
    mapped = {(r.get("file", ""), r.get("function", "")) for r in _rows(code_map)}
    return [f"{f}\t{fn}\t\t\t" for f, fn in sorted(functions_on_disk(root) - mapped)]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--missing", action="store_true", help="print rows to add for unmapped functions")
    args = ap.parse_args(argv)
    if args.missing:
        print("\n".join(missing_rows()))
        return 0
    problems = check()
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s); {len(functions_on_disk())} functions on disk")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
