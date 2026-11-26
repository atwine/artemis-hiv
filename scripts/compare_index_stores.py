"""Do the kept Chroma index and the in-memory store Phase 2B was measured with find the same passages?

    python scripts/compare_index_stores.py

The keep rule for plan item 4.3, written before the run (owner, 2026-11-26): for every search,
Chroma returns the same top 5 passages in the same order as the in-memory store. The searches are
Phase 2B's 20 questions (eval/phase2b/questions.json) and every search question the AI wrote in
GLM's final run (eval/phase2/runs/glm-5.2-t0-5q). Writes eval/phase4/index-store-check.txt.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "eval" / "phase4" / "index-store-check.txt"
TOP_K = 5


def searches() -> list:
    out = [q["question"] for q in json.loads((ROOT / "eval" / "phase2b" / "questions.json").read_text(encoding="utf-8"))["questions"]]
    for f in sorted(glob.glob(str(ROOT / "eval" / "phase2" / "runs" / "glm-5.2-t0-5q" / "*.json"))):
        out += json.loads(Path(f).read_text(encoding="utf-8"))["screening"].get("search_questions") or []
    return out


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    import app
    from artemis.guidelines.vector_store import ChromaVectorStore, InMemoryVectorStore
    from modules.rag_engine import RagEngine

    kept = app._get_rag_engine(prefer_chroma=True, embedding_model_name=app.EMBEDDING_MODEL, engine_version=5)
    if not isinstance(kept._vector_store, ChromaVectorStore) or not kept.search_ready:
        print("Chroma or the search model did not start; nothing compared.")
        return 1
    kept.ensure_indexed()
    measured = RagEngine(project_root=ROOT, guideline_paths=app.GUIDELINE_PATHS, embedder=kept._embedder,
                         vector_store=InMemoryVectorStore())
    measured.ensure_indexed()

    qs = searches()
    same_order = same_set = 0
    differing = []
    for q in qs:
        a = [r.chunk_id for r in measured._vector_store.query(q, kept._embedder, top_k=TOP_K)]
        b = [r.chunk_id for r in kept._vector_store.query(q, kept._embedder, top_k=TOP_K)]
        same_order += a == b
        same_set += set(a) == set(b)
        if a != b:
            differing.append((q, a, b))
    lines = [
        f"Kept Chroma index vs the in-memory store Phase 2B measured ({app.EMBEDDING_MODEL}, top {TOP_K}).",
        f"Searches: {len(qs)} (20 Phase 2B questions + {len(qs) - 20} AI-written questions from GLM's final run).",
        f"Same passages in the same order: {same_order}/{len(qs)}",
        f"Same passages, any order: {same_set}/{len(qs)}",
        f"Keep rule (same order for every search): {'MET' if same_order == len(qs) else 'NOT MET'}",
    ]
    for q, a, b in differing[:20]:
        lines += ["", f"Differs: {q}", f"  in-memory: {a}", f"  chroma:    {b}"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:5]))
    return 0 if same_order == len(qs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
