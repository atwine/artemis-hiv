"""Print the backend's OpenAPI schema, so the website's types are generated from it.

Run from web/: `npm run api:types` (writes src/lib/api/schema.d.ts) or `npm run api:check`
(fails if the committed types no longer match the backend). Builds the app without a database
or model; nothing is started, loaded or called.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.main import create_app  # noqa: E402
from backend.services import Services  # noqa: E402
from backend.settings import Settings  # noqa: E402


def main() -> None:
    unused = Services(patients=list, search=lambda: None, model_client=lambda: None, engine=None, app_version="schema")
    schema = create_app(settings=Settings(), services=unused).openapi()
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)


if __name__ == "__main__":
    main()
