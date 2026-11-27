"""Streamlit is gone (owner, 2026-11-27: "i want it totally erased"; plans 4C.1 and 4C.6).

The app is the website and the backend. No Python file in the repo imports Streamlit or the old
Streamlit app, the requirements don't list it, and the app's old files are gone. The app's setup
(guideline files, search model, index) lives in artemis/config.py.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GONE = {"streamlit", "app", "ui", "agentic_demo", "run_baseline", "pandas", "ollama"}
SKIP = {".git", ".venv", "venv", "node_modules", "web", ".claude"}  # web/ is the website's own code


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module.split(".")[0]


def _python_files():
    for path in sorted(ROOT.rglob("*.py")):
        if not SKIP & set(path.relative_to(ROOT).parts):
            yield path


def test_no_python_file_imports_streamlit_or_the_old_app():
    found = [f"{p.relative_to(ROOT).as_posix()}: {name}" for p in _python_files() for name in set(_imports(p)) & GONE]
    assert found == []


def test_the_requirements_have_no_streamlit():
    for name in ("requirements.in", "requirements.txt"):
        listed = [line.split("==")[0].strip().lower() for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.lstrip().startswith("#")]
        assert not {"streamlit", "pandas", "ollama"} & set(listed), name
    assert "streamlit" not in (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()


def test_the_old_app_files_are_gone():
    for rel in ("app.py", "ui", "agentic_demo.py", "artemis/visit_record.py", "artemis/session_keys.py",
                "Data/mock_patients.json", "Data/custom_patients.json", "Data/demo_day_patients.json",
                "Data/demo_clinic_day.json", "scripts/run_baseline.py", "scripts/load_patients.py"):
        assert not (ROOT / rel).exists(), rel


def test_ci_does_not_run_streamlit():
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        assert "streamlit" not in wf.read_text(encoding="utf-8").lower(), wf.name


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
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('streamlit', 'app', 'run_baseline', 'ui', 'ollama')))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "[]"


def test_the_backend_searches_the_same_index_the_app_did():
    """Same guideline files, search model and index version as the old app used (index name unchanged)."""
    from artemis import config
    from artemis.guidelines.vector_store import index_collection_name

    assert config.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
    assert config.GUIDELINE_INDEX_VERSION == 3
    assert [p.name for p in config.GUIDELINE_PATHS]  # the Ugandan guidelines
    assert all(p.is_file() for p in config.GUIDELINE_PATHS)
    name = index_collection_name(config.EMBEDDING_MODEL, config.GUIDELINE_PATHS, config.GUIDELINE_INDEX_VERSION)
    # The middle part is a fingerprint of the guideline files' bytes, which differ between a Windows
    # checkout (CRLF) and GitHub's Linux one (LF), so only the parts that name the model and the
    # version are pinned here (owner, 2026-11-27: fix the test only; the line-ending fix is on the
    # plan's Later list).
    assert name.startswith("guidelines_all-minilm-l6-v2_") and name.endswith("_v3")
