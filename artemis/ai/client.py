"""The model client.

OpenAICompatClient talks to any OpenAI-compatible server: vLLM on the A100, OpenRouter, or a
local Ollama through its OpenAI-compatible endpoint (for the fine-tuning experiments). It is
selected by setting LLM_BASE_URL (see `openai_compat_config_from_env`). `.chat(...)` returns a
`ChatReply`: the text with why it ended, any error, a note and the usage, all for that one call
(plan item 4.6). The native Ollama client the Streamlit screen used went with it (plan 4C.6).
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, ClassVar, Dict, List, Optional, Protocol, TypedDict
from urllib.parse import urlsplit

# The AI runs without added randomness, so the same record gets the same alerts (owner, G38,
# 2026-11-25). Measured on Llama: at 0, 10 of 11 test patients got the same alerts on all 5 runs,
# against 4 of 11 at 0.2, with catches and false alarms about the same (eval/phase2/README.md).
DEFAULT_TEMPERATURE = 0.0


class ChatMessage(TypedDict):
    role: str
    content: str


@dataclass(frozen=True)
class ChatReply:
    """One call's reply, and everything about it (plan item 4.6: no state left on the client).

    text: the reply, or None when there is no usable one (then `error` says why).
    finish_reason: the server's own word (fix 8): "stop" (the model finished) or "length" (cut
    at the token limit); None when the server didn't say.
    error: why there is no reply, without the server's address (fix 10, G26).
    note: anything worth knowing, such as a retry without the answer format.
    usage: what the server reported (tokens, and the cost when it sends one).
    """

    text: Optional[str]
    finish_reason: Optional[str] = None
    error: Optional[str] = None
    note: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


def _hide_address(text: str, url: str) -> str:
    """Error text without the server's address, which lives only in .env (fix 10, G26)."""
    parts = urlsplit(url if "://" in url else f"http://{url}")
    for secret in sorted({url, url.rstrip("/"), parts.netloc, parts.hostname or ""}, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "<model server>")
    return text


class ChatClient(Protocol):
    """What the analysis needs from a model client: its name, and one chat call."""

    @property
    def model(self) -> str: ...

    def chat(self, messages: List[ChatMessage], *, format: Optional[Any] = None,
             options_override: Optional[Dict[str, Any]] = None) -> ChatReply: ...


@dataclass(frozen=True)
class OpenAICompatConfig:
    # Example: http://<vllm-host>:8000/v1 (the path up to and including /v1).
    base_url: str
    # None means "use the first model the server lists".
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout_s: float = 600.0
    # Phase 2: a fixed temperature (None keeps DEFAULT_TEMPERATURE), and extra request fields such as
    # OpenRouter's {"reasoning": {"enabled": False}, "usage": {"include": True}}.
    temperature: Optional[float] = None
    extra_body: Optional[Dict[str, Any]] = None


def openai_compat_config_from_env() -> Optional[OpenAICompatConfig]:
    """Read LLM_BASE_URL / LLM_MODEL / LLM_API_KEY. None when LLM_BASE_URL is unset."""

    base_url = (os.getenv("LLM_BASE_URL") or "").strip().rstrip("/")
    if not base_url:
        return None
    return OpenAICompatConfig(
        base_url=base_url,
        model=(os.getenv("LLM_MODEL") or "").strip() or None,
        api_key=(os.getenv("LLM_API_KEY") or "").strip() or None,
    )


def _text_of(content: Any) -> Optional[str]:
    """The reply text. Some servers send it as a list of parts ({"type": "text", "text": ...})."""
    if isinstance(content, list):
        return "".join(str(part.get("text") or "") for part in content if isinstance(part, dict))
    return content


class OpenAICompatClient:
    """Chat client for OpenAI-compatible servers (vLLM, llama.cpp server, LM Studio).

    Accepts the same Ollama-style options the pipeline already passes and maps the
    ones that have an equivalent. repeat_penalty, repeat_last_n and num_ctx are
    dropped: they were tuned for a 4B local model, vLLM's repetition_penalty uses a
    different scale, and the server fixes its own context length.
    """

    _OPTION_MAP: ClassVar[Dict[str, str]] = {
        "temperature": "temperature",
        "num_predict": "max_tokens",
        "top_p": "top_p",
        "top_k": "top_k",
        "seed": "seed",
    }

    def __init__(self, config: OpenAICompatConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._configured_model = config.model
        self._resolved_model: Optional[str] = config.model
        self._api_key = config.api_key
        self._timeout_s = config.timeout_s
        self._temperature = config.temperature
        self._extra_body = dict(config.extra_body or {})

    @property
    def model(self) -> str:
        return self._resolved_model or self._configured_model or "(server default)"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _resolve_model(self) -> str:
        if self._resolved_model:
            return self._resolved_model
        import requests

        resp = requests.get(f"{self._base_url}/models", headers=self._headers(), timeout=15)
        resp.raise_for_status()
        models = [m.get("id") for m in resp.json().get("data", []) if m.get("id")]
        # Rationale: guessing is safe only when the server serves one model (vLLM).
        # Hosted gateways such as OpenRouter list hundreds, so the first one is arbitrary.
        if len(models) != 1:
            raise RuntimeError(
                f"{len(models)} models listed by the model server; set LLM_MODEL to pick one"
            )
        self._resolved_model = models[0]
        return self._resolved_model

    @staticmethod
    def _response_format(format: Optional[Any]) -> Optional[Dict[str, Any]]:
        # Ollama's `format` is "json" or a JSON schema; map both to OpenAI's response_format.
        if format == "json":
            return {"type": "json_object"}
        if isinstance(format, dict):
            return {"type": "json_schema", "json_schema": {"name": "response", "schema": format}}
        return None

    def chat(
        self,
        messages: List[ChatMessage],
        *,
        format: Optional[Any] = None,
        options_override: Optional[Dict[str, Any]] = None,
    ) -> ChatReply:
        try:
            import requests
        except Exception:
            return ChatReply(None, error="Python package 'requests' is not available in this environment")

        note: Optional[str] = None
        try:
            options: Dict[str, Any] = {
                "temperature": DEFAULT_TEMPERATURE if self._temperature is None else self._temperature,
                "num_predict": 128,
            }
            if options_override:
                options.update(options_override)

            body: Dict[str, Any] = {**self._extra_body, "model": self._resolve_model(), "messages": list(messages)}
            for src, dst in self._OPTION_MAP.items():
                if options.get(src) is not None:
                    body[dst] = options[src]
            response_format = self._response_format(format)
            if response_format is not None:
                body["response_format"] = response_format

            url = f"{self._base_url}/chat/completions"
            resp = requests.post(url, json=body, headers=self._headers(), timeout=self._timeout_s)
            if resp.status_code in (400, 404, 422) and "response_format" in body:
                # Some servers reject schema-constrained output (vLLM: 400; OpenRouter:
                # 404 "no endpoints found" for models without it); the pipeline's JSON
                # parsers already cope with free-text JSON, so retry without it.
                note = (
                    f"The server refused the answer format (HTTP {resp.status_code}), "
                    "so the model was asked again without it."
                )
                body.pop("response_format")
                resp = requests.post(url, json=body, headers=self._headers(), timeout=self._timeout_s)
            resp.raise_for_status()

            reply = resp.json()
            usage = reply.get("usage")
            choices = reply.get("choices") or []
            choice = choices[0] if choices else {}
            finish = choice.get("finish_reason")
            content = _text_of((choice.get("message") or {}).get("content"))
            if not content:
                return ChatReply(None, finish_reason=finish, error="Model server returned an empty message content",
                                 note=note, usage=usage)
            return ChatReply(content, finish_reason=finish, note=note, usage=usage)
        except Exception as e:
            return ChatReply(None, note=note,
                             error=f"Model server call failed: {type(e).__name__}: {_hide_address(str(e), self._base_url)}")
