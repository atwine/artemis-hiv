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


# LLM_REASONING (owner, 2026-11-27): GLM on OpenRouter runs with its thinking off, as it was measured.

def _config_from(monkeypatch, **env):
    from artemis.ai.client import openai_compat_config_from_env

    monkeypatch.setenv("LLM_BASE_URL", "http://example.invalid/v1")
    monkeypatch.delenv("LLM_REASONING", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return openai_compat_config_from_env()


def test_reasoning_off_asks_the_server_to_skip_thinking(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests
    from artemis.ai.client import OpenAICompatClient

    sent = {}
    monkeypatch.setattr(requests, "post", lambda url, json=None, headers=None, timeout=None: (sent.update(json), _Resp())[1])
    OpenAICompatClient(_config_from(monkeypatch, LLM_REASONING="off", LLM_MODEL="m")).chat([{"role": "user", "content": "hi"}])
    assert sent["reasoning"] == {"enabled": False}


@pytest.mark.parametrize("env", [{}, {"LLM_REASONING": ""}, {"LLM_REASONING": "  "}])
def test_without_the_setting_thinking_is_off(monkeypatch: pytest.MonkeyPatch, env) -> None:
    # Owner, 2026-11-27: "Turn off the thinking completely". Thinking on spent every call's reply
    # room on thinking (GLM 5.2, measured); the A100's vLLM accepts the switch and ignores it.
    assert _config_from(monkeypatch, **env).extra_body == {"reasoning": {"enabled": False}}


@pytest.mark.parametrize("value", ["OFF", " off "])
def test_off_is_read_whatever_its_case_or_spaces(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    assert _config_from(monkeypatch, LLM_REASONING=value).extra_body == {"reasoning": {"enabled": False}}


def test_reasoning_on_asks_the_server_to_think(monkeypatch: pytest.MonkeyPatch) -> None:
    # The thinking on/off experiment (owner, 2026-11-27): GLM's own default effort, asked for outright.
    assert _config_from(monkeypatch, LLM_REASONING=" On ").extra_body == {"reasoning": {"enabled": True}}


@pytest.mark.parametrize("value", ["true", "false", "yes", "disabled", "of"])
def test_any_other_value_is_refused_so_a_typo_cant_leave_thinking_on(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValueError, match="LLM_REASONING"):
        _config_from(monkeypatch, LLM_REASONING=value)
