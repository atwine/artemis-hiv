"""Phase 2: the model client can set temperature, send extra request fields, and report usage."""

from __future__ import annotations

import pytest


class _Resp:
    status_code = 200

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "[]"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0001}}


def test_temperature_extra_fields_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests
    from artemis.ai.client import OpenAICompatClient, OpenAICompatConfig

    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):  # noqa: A002
        sent.update(json)
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    client = OpenAICompatClient(OpenAICompatConfig(
        base_url="http://example.invalid/v1", model="m", temperature=0.0,
        extra_body={"reasoning": {"enabled": False}, "usage": {"include": True}, "model": "not-this"},
    ))
    reply = client.chat([{"role": "user", "content": "hi"}], options_override={"num_predict": 50})
    assert reply.text == "[]"
    assert sent["temperature"] == 0.0 and sent["max_tokens"] == 50
    assert sent["reasoning"] == {"enabled": False} and sent["usage"] == {"include": True}
    assert sent["model"] == "m"  # extra fields never replace the model or the messages
    assert reply.usage == {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.0001}


def test_the_server_client_runs_at_temperature_0_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # Owner's pick (G38): at 0, 10 of 11 test patients got the same alerts on every run, against 4 of 11 at 0.2.
    import requests
    from artemis.ai.client import OpenAICompatClient, OpenAICompatConfig

    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, headers=None, timeout=None: (sent.update(json), _Resp())[1])
    OpenAICompatClient(OpenAICompatConfig(base_url="http://example.invalid/v1", model="m")).chat([{"role": "user", "content": "hi"}])
    assert sent["temperature"] == 0 and "reasoning" not in sent
