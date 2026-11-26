"""The API's published shape matches docs/api/openapi.json, which the website builds its types from.

When this fails after a deliberate change, run `python scripts/export_openapi.py`, read the diff
of docs/api/openapi.json, and commit it with the change (and tell the website session).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "scripts" / "export_openapi.py")
export = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export)  # type: ignore[union-attr]


# FastAPI's own error shapes, which differ between FastAPI versions (this laptop vs the locked
# one GitHub installs); every other part of the shape is ours and is compared exactly.
_FRAMEWORK = {"ValidationError", "HTTPValidationError"}


def _ours(schema: dict) -> dict:
    out = json.loads(json.dumps(schema))
    for name in _FRAMEWORK:
        out.get("components", {}).get("schemas", {}).pop(name, None)
    return out


def test_the_published_shape_has_not_changed_by_accident():
    saved = json.loads(export.SNAPSHOT.read_text(encoding="utf-8"))
    assert _ours(export.schema()) == _ours(saved), (
        "The API's shape changed: run scripts/export_openapi.py (with the locked package versions) and review the diff."
    )


def test_every_route_in_the_shape_is_in_access_md():
    import re

    paths = json.loads(export.SNAPSHOT.read_text(encoding="utf-8"))["paths"]
    access = (ROOT / "ACCESS.md").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\| (?:GET|POST|PUT|PATCH|DELETE) \| (\S+) \|", access, re.MULTILINE))
    assert set(paths) == listed
