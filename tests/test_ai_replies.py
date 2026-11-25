"""Fix 8: the AI's replies are read correctly, and nothing is cut, merged or dropped."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, Optional

import pytest

from artemis.ai.screening import generate_llm_screening_alerts
from artemis.patient.record import build_patient_context
from artemis.patient.summary import build_stage1_summary
from artemis.guidelines.vector_store import VectorSearchResult
from tests import pipeline_harness as h


def _alert(i: int, **kw: Any) -> Dict[str, Any]:
    base = {
        "alert_id": f"A{i}",
        "title": f"Alert {i}",
        "message": f"Message {i}.",
        "issue_type": "monitoring_gap",
        "severity": "moderate",
        "recommended_action": "Act.",
        "citations": [{"page_number": 1, "chunk_id": "c1"}],
    }
    base.update(kw)
    return base


CHUNKS = [VectorSearchResult(chunk_id="c1", document="Guideline text one.", metadata={"page_number": 1}, distance=0.1)]


class Model:
    model = "stub"

    def __init__(self, reply: Optional[str], *, finish: str = "stop", error: Optional[str] = None) -> None:
        self.reply, self.last_error, self.last_finish_reason = reply, error, finish

    def chat(self, messages, format=None, options_override=None):  # noqa: A002
        return self.reply


def _screen(reply: Optional[str], *, finish: str = "stop"):
    p = copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == "P001"))
    ctx = build_patient_context(p)
    debug: Dict[str, Any] = {}
    alerts = generate_llm_screening_alerts(
        patient_context=ctx,
        stage1_summary=build_stage1_summary(patient=p, context=ctx),
        screening_chunks=CHUNKS,
        llm_client=Model(reply, finish=finish),
        debug=debug,
    )
    return alerts, debug


# 8a: reading the reply

def test_a_bracketed_reference_before_the_list_is_not_read_as_the_list() -> None:
    alerts, debug = _screen("Based on guideline [1], here are the alerts: " + json.dumps([_alert(1)]))
    assert [a.title for a in alerts] == ["Alert 1"]
    assert debug["parse_status"] == "parsed_nonempty"


def test_a_single_alert_sent_without_a_list_is_read_as_one_alert() -> None:
    alerts, _ = _screen(json.dumps(_alert(1)))
    assert [a.title for a in alerts] == ["Alert 1"]


def test_alerts_written_as_plain_strings_are_unreadable_not_empty() -> None:
    alerts, debug = _screen(json.dumps(["Viral load overdue", "Check creatinine"]))
    assert alerts == []
    assert debug["parse_status"] == "parse_failed"


def test_a_reply_cut_off_partway_keeps_the_complete_alerts_and_says_it_was_cut() -> None:
    full = json.dumps([_alert(1), _alert(2)])
    alerts, debug = _screen(full[: full.index('"Message 2')], finish="length")
    assert [a.title for a in alerts] == ["Alert 1"]
    assert debug["parse_status"] == "cut_off"


def test_the_client_reports_a_reply_the_server_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from artemis.ai.client import OpenAICompatClient, OpenAICompatConfig

    class Resp:
        status_code = 200

        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"choices": [{"message": {"content": [{"type": "text", "text": "[1"}]}, "finish_reason": "length"}]}

    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: Resp())
    client = OpenAICompatClient(OpenAICompatConfig(base_url="http://example.invalid/v1", model="m"))
    assert client.chat([{"role": "user", "content": "hi"}]) == "[1"  # list-of-parts content is joined
    assert client.last_finish_reason == "length"


def test_a_cut_off_review_is_never_green() -> None:
    from artemis.visit import AnalysisOptions, run_visit_analysis
    from modules.rag_engine import RagEngine

    full = json.dumps([_alert(1), _alert(2)])
    p = copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == "P002"))
    rag = RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore([]))
    result = run_visit_analysis(
        patient=p, today_note="", rag=rag, llm_client=Model(full[:5], finish="length"), options=AnalysisOptions()
    )
    assert result.screening_outcome == "cut_off"
    assert result.status != "GREEN"


# 8b: the alerts themselves

def test_different_alerts_with_similar_titles_are_both_kept() -> None:
    alerts, _ = _screen(
        json.dumps(
            [
                _alert(1, title="Possible TDF renal toxicity", message="Creatinine rising."),
                _alert(2, title="Possible EFV CNS toxicity", message="Vivid dreams on EFV."),
            ]
        )
    )
    assert [a.title for a in alerts] == ["Possible TDF renal toxicity", "Possible EFV CNS toxicity"]


def test_messages_are_shown_as_written() -> None:
    msg = "Hb 9.1 then 7.2 g/dL. Hb 9.1 then 7.2 g/dL is falling. Creatinine 1.4 mg/dL."
    alerts, _ = _screen(json.dumps([_alert(1, message=msg)]))
    assert alerts[0].message == msg


def test_only_exact_repeats_are_dropped_and_clashing_ids_are_kept_apart() -> None:
    alerts, _ = _screen(json.dumps([_alert(1), _alert(1), _alert(1, title="Other", message="Different.")]))
    assert [a.title for a in alerts] == ["Alert 1", "Other"]
    assert len({a.alert_id for a in alerts}) == 2


@pytest.mark.parametrize("written, stored", [("severe", "not given"), ("", "not given"), (" High ", "high")])
def test_severity_is_one_of_the_four_or_not_given(written: str, stored: str) -> None:
    alerts, _ = _screen(json.dumps([_alert(1, severity=written)]))
    assert alerts[0].evidence["severity"] == stored


def test_a_citation_to_a_passage_the_ai_was_not_shown_is_marked() -> None:
    alerts, _ = _screen(
        json.dumps([_alert(1, citations=[{"page_number": 1, "chunk_id": "c1"}, {"page_number": 99, "chunk_id": "made_up"}])])
    )
    shown = {c["chunk_id"]: c["shown_to_ai"] for c in alerts[0].evidence["citations"]}
    assert shown == {"c1": True, "made_up": False}


def test_an_ai_alerts_references_are_the_passages_it_was_shown_and_cited() -> None:
    from artemis.visit import AnalysisOptions, run_visit_analysis
    from modules.rag_engine import RagEngine

    corpus = [
        {"chunk_id": "c1", "document": "creatinine viral load monitoring", "metadata": {"page_number": 1}},
        {"chunk_id": "c2", "document": "other text about regimen labs", "metadata": {"page_number": 2}},
    ]
    p = copy.deepcopy(next(x for x in h.patients() if x["patient_id"] == "P002"))
    rag = RagEngine(project_root=h.ROOT, guideline_paths=[], embedder=h.FakeEmbedder(), vector_store=h.FakeStore(corpus))
    reply = json.dumps([_alert(1, citations=[{"page_number": 1, "chunk_id": "c1"}])])
    result = run_visit_analysis(patient=p, today_note="", rag=rag, llm_client=Model(reply), options=AnalysisOptions())
    ai = next(r for r in result.results if r["alert"].source == "ai")
    assert [c.chunk_id for c in ai["retrieved"]] == ["c1"]


def test_a_reply_cut_inside_a_citation_keeps_the_complete_alerts() -> None:
    two = [{"page_number": 1, "chunk_id": "c1"}, {"page_number": 2, "chunk_id": "c2"}]
    full = json.dumps([_alert(1, citations=two), _alert(2, citations=two)])
    alerts, debug = _screen(full[: full.rindex('"c2"') + 2])
    assert [a.title for a in alerts] == ["Alert 1"]
    assert debug["parse_status"] == "cut_off"


def test_an_unreadable_item_in_the_list_keeps_the_rest_and_says_so() -> None:
    alerts, debug = _screen("[" + json.dumps(_alert(1)) + ', "oops", ' + json.dumps(_alert(2)) + "]")
    assert [a.title for a in alerts] == ["Alert 1", "Alert 2"]
    assert debug["parse_status"] == "partly_read"
    alerts, debug = _screen("[" + json.dumps(_alert(1)) + ", {'title': 'single quotes'}]")
    assert [a.title for a in alerts] == ["Alert 1"]
    assert debug["parse_status"] == "partly_read"


def test_an_alert_with_no_title_or_message_is_shown_and_says_so() -> None:
    alerts, _ = _screen(json.dumps([_alert(1, title="", message=" ")]))
    assert alerts[0].title == "AI alert with no title"
    assert alerts[0].message == "The AI gave no explanation for this alert."
