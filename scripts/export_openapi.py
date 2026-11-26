"""Write the backend's published shape (its OpenAPI schema) to docs/api/openapi.json.

The Next.js site generates its types from this shape, so it must change only on purpose:
tests/test_openapi_snapshot.py fails when the live API and this file differ. After changing a
route or a model on purpose, rerun this and commit the new file with the change.

    python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SNAPSHOT = ROOT / "docs" / "api" / "openapi.json"


def schema() -> dict:
    from backend.main import create_app
    from backend.services import Services
    from backend.settings import Settings

    # The shape doesn't depend on the services, so nothing real is loaded or connected.
    services = Services(patients=list, search=lambda: None, model_client=lambda: None, engine=None, app_version="schema")
    return create_app(settings=Settings(), services=services).openapi()


def render() -> str:
    return json.dumps(schema(), indent=1, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(render(), encoding="utf-8")
    print(f"wrote {SNAPSHOT.relative_to(ROOT)}")
