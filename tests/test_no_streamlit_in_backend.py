"""Plan 4C.1: the backend and the evaluation run without the Streamlit app (owner, 2026-11-27).

The app's setup (guideline files, search model, index) lives in artemis/config.py. Nothing in
backend/, artemis/ or the evaluation scripts loads app.py or streamlit. run_baseline.py drives the
Streamlit screen's own analysis by design and goes with Streamlit (4C.6).
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STREAMLIT_ONLY = {"scripts/run_baseline.py"}  # removed with Streamlit (4C.6)


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module.split(".")[0]


def test_no_backend_artemis_or_script_code_imports_the_streamlit_app():
    found = []
    for folder in ("backend", "artemis", "scripts"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel in STREAMLIT_ONLY:
                continue
            found += [f"{rel}: {name}" for name in set(_imports(path)) & {"app", "streamlit", "run_baseline", "ui"}]
    assert found == []


def test_the_backend_and_the_evaluation_scripts_start_without_streamlit():
    code = (
        "import sys, importlib.util\n"
        f"sys.path.insert(0, {str(ROOT)!r}); sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
        "from backend.main import create_app\n"
        "from backend.settings import Settings\n"
        "import backend.services, artemis.config\n"
        "create_app(settings=Settings())\n"
        "for name in ('build_index', 'check_phase4', 'compare_index_stores', 'run_phase2', 'check_retrieval'):\n"
        "    importlib.import_module(name)\n"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('streamlit', 'app', 'run_baseline', 'ui')))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


def test_the_backend_searches_the_same_index_the_app_did():
    """Same guideline files, search model and index version as app.py used (index name unchanged)."""
    from artemis import config
    from artemis.guidelines.vector_store import index_collection_name

    assert config.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
    assert config.GUIDELINE_INDEX_VERSION == 3
    assert [p.name for p in config.GUIDELINE_PATHS]  # the Ugandan guidelines
    assert all(p.is_file() for p in config.GUIDELINE_PATHS)
    name = index_collection_name(config.EMBEDDING_MODEL, config.GUIDELINE_PATHS, config.GUIDELINE_INDEX_VERSION)
    # The kept index's name as app.py computed it before the move (2026-11-27): unchanged, so the
    # index already on disk is reused, not rebuilt.
    assert name == "guidelines_all-minilm-l6-v2_1e4068fad8a4_v3"
