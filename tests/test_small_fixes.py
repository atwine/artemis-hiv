"""Fix 10: small faults that changed what the AI reads, what is stored, or what the code reports."""

from __future__ import annotations

import copy
from typing import Any, Dict, List


from artemis.ai.client import ChatReply
from artemis.guidelines.processor import GuidelineChunk, _strip_markdown_noise as clean
from artemis.guidelines.vector_store import InMemoryVectorStore
from tests import pipeline_harness as h


class _LengthEmbedder:
    loaded = True

    def encode(self, texts: List[str]) -> List[List[float]]:
        return [[float(len(t)), float(t.count("a")) + 1.0] for t in texts]


# G29: the guideline text cleaner

def test_the_cleaner_keeps_thresholds_written_with_angle_brackets() -> None:
    for text in (
        "If VL < 50 copies/mL and CD4 > 200, continue.",
        "VL<50 and CD4>200",
        "Refer if ALT <ULN and AST> 3x normal.",
    ):
        assert clean(text) == text


def test_the_cleaner_still_removes_html_tags_and_keeps_table_cells() -> None:
    out = clean("Line one<br>line two <sup>1</sup><table><tr><td>VL</td><td>&lt;50</td></tr></table>")
    assert "<br>" not in out and "<sup>" not in out and "<td>" not in out
    assert "line two" in out and "VL" in out and "<50" in out


def test_text_inside_figure_blocks_is_kept_and_logos_are_dropped() -> None:
    raw = (
        "<::icon of two figures. The following text is presented: | Recommendation 2025 | "
        "DTG+3TC can be used for treatment simplification: figure::>\n"
        "<::logo: [Unknown] MODULE 9 ART::>"
    )
    out = clean(raw)
    assert "Recommendation 2025" in out and "DTG+3TC can be used for treatment simplification" in out
    assert ": figure" not in out
    assert "MODULE 9" not in out


# G30: the backup guideline store

def test_the_backup_store_keeps_every_guideline_file() -> None:
    store = InMemoryVectorStore()
    emb = _LengthEmbedder()
    first = [GuidelineChunk(chunk_id=f"uganda__{i}", text=f"uganda text {i}", source_path="uganda.md", page_number=i) for i in range(3)]
    second = [GuidelineChunk(chunk_id=f"who__{i}", text=f"who text {i}", source_path="who.md", page_number=i) for i in range(2)]
    store.index_guidelines(first, emb)  # type: ignore[arg-type]
    store.index_guidelines(second, emb)  # type: ignore[arg-type]
    store.index_guidelines(first, emb)  # type: ignore[arg-type]  # indexing a file again doesn't duplicate it
    found = store.query("anything", emb, top_k=100)  # type: ignore[arg-type]
    assert sorted(r.chunk_id for r in found) == sorted([c.chunk_id for c in first + second])


# D16: the plan step reads dated lab values, with no trend labels

class _Capture:
    model = "capture"

    def __init__(self) -> None:
        self.calls: List[List[Dict[str, Any]]] = []

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        self.calls.append(messages)
        return ChatReply("[]" if isinstance(format, dict) else "{}", finish_reason="stop")


def test_the_plan_step_reads_dated_lab_values_without_trend_labels() -> None:
    from artemis.visit import AnalysisOptions, run_visit_analysis
    from modules.rag_engine import RagEngine

    p = copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == "P002"))
    rag = RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))
    model = _Capture()
    run_visit_analysis(patient=p, today_note="", rag=rag, llm_client=model, options=AnalysisOptions(agentic=True))
    # The plan prompts carry the patient (the repair retry only carries the draft plan).
    plan_prompts = [m["content"] for call in model.calls for m in call if m["role"] == "user" and "Patient id: P002" in m["content"]]
    assert plan_prompts
    for text in plan_prompts:
        assert "Lab trends" not in text and "FALLING" not in text and "RISING" not in text
        assert "2024-09-15" in text and "2025-09-15" in text  # both viral loads, with their dates


# G26: the model server's address stays off the screen

def test_error_text_does_not_show_the_model_servers_address() -> None:
    from artemis.ai.client import OpenAICompatClient, OpenAICompatConfig

    client = OpenAICompatClient(OpenAICompatConfig(base_url="http://127.0.0.1:9/v1", model="m", timeout_s=3))
    reply = client.chat([{"role": "user", "content": "hi"}])
    assert reply.text is None
    assert reply.error and "127.0.0.1" not in reply.error
