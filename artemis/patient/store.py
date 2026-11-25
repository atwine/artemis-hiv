"""Saved lists on disk: the added patient cases and the candidate rules (fix 10, G16).

A file that exists but can't be read is reported, never treated as empty: treating it as
empty let the next save overwrite every saved case. Writes go to a temporary file that then
replaces the old one, so a crash mid-write leaves the old file whole.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List


class UnreadableFile(Exception):
    """The file exists but isn't a JSON list of objects."""


def read_json_list(path: Path) -> List[Dict[str, Any]]:
    """The saved list, or [] when the file doesn't exist yet. Raises UnreadableFile otherwise."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnreadableFile(f"{path.name}: {type(exc).__name__}") from exc
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise UnreadableFile(f"{path.name}: not a list of records")
    return data


def write_json_list(path: Path, items: List[Dict[str, Any]]) -> None:
    """Replace the file with `items` in one step. Raises OSError when it can't be written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(items, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
