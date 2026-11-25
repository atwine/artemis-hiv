"""LLM clients.

Two backends share one interface (`.model`, `.last_error`, `.last_finish_reason`,
`.last_note`, `.chat(...)`):
- OllamaClient: a local Ollama server (the original setup).
- OpenAICompatClient: any OpenAI-compatible server, such as vLLM on a remote GPU.
  Selected by setting LLM_BASE_URL (see `openai_compat_config_from_env`).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TypedDict
from urllib.parse import urlsplit

# The AI runs without added randomness, so the same record gets the same alerts (owner, G38,
# 2026-11-25). Measured on Llama: at 0, 10 of 11 test patients got the same alerts on all 5 runs,
# against 4 of 11 at 0.2, with catches and false alarms about the same (eval/phase2/README.md).
DEFAULT_TEMPERATURE = 0.0


class ChatMessage(TypedDict):
    role: str
    content: str


class _ReplyState:
    """Why the last reply ended and anything worth noting about it (fix 8).

    last_finish_reason is the server's own word: "stop" (the model finished) or
    "length" (the server cut the reply at the token limit). None when the server
    did not say.
    """

    _last_finish_reason: Optional[str] = None
    _last_note: Optional[str] = None

    @property
    def last_finish_reason(self) -> Optional[str]:
        return self._last_finish_reason

    @property
    def last_note(self) -> Optional[str]:
        return self._last_note


def _hide_address(text: str, url: str) -> str:
    """Error text without the server's address, which lives only in .env (fix 10, G26)."""
    parts = urlsplit(url if "://" in url else f"http://{url}")
    for secret in sorted({url, url.rstrip("/"), parts.netloc, parts.hostname or ""}, key=len, reverse=True):
        if secret:
            text = text.replace(secret, "<model server>")
    return text


def ollama_host() -> str:
    """The Ollama address from OLLAMA_HOST, as the client will use it.

    OLLAMA_HOST is often a bind address such as 0.0.0.0:11434, which a client can't connect
    to, so 0.0.0.0 becomes localhost; the scheme (http or https) is kept (fix 10, G28).
    """
    raw = (os.getenv("OLLAMA_HOST") or "").strip()
    if not raw:
        return "http://localhost:11434"
    host = raw if "://" in raw else f"http://{raw}"
    return host.replace("://0.0.0.0", "://localhost")


def list_ollama_models() -> Tuple[List[str], Optional[str]]:
    """The models installed on the local Ollama server, and an error message when it can't be reached."""
    try:
        from ollama import Client
    except Exception:
        return [], "the Python package 'ollama' is not installed"
    try:
        resp = Client(host=ollama_host(), timeout=5.0).list()
    except Exception as exc:
        return [], f"{type(exc).__name__}"
    items: Any = getattr(resp, "models", None)
    if items is None:
        items = (resp.get("models") or resp.get("data") or []) if isinstance(resp, dict) else resp
    names: List[str] = []
    for item in items if isinstance(items, list) else []:
        name = getattr(item, "name", None) or getattr(item, "model", None)
        if name is None and isinstance(item, dict):
            name = item.get("name") or item.get("model")
        if name is None and isinstance(item, str):
            name = item
        if isinstance(name, str) and name:
            names.append(name)
    return names, None


@dataclass(frozen=True)
class OllamaConfig:
    # Rationale: default to the locally pulled model tag to avoid mismatches.
    model: str = "aadide/medgemma-1.5-4b-it-Q4_K_S"
    # Rationale: allow setting the context window per request without changing server env.
    # Matches Ollama `num_ctx` parameter. [src]
    # - https://raw.githubusercontent.com/ollama/ollama/main/docs/modelfile.mdx#valid-parameters-and-values
    # 8192, as on the settings panel; Ollama's own default is smaller and cuts long prompts (fix 10).
    num_ctx: Optional[int] = 8192


class OllamaClient(_ReplyState):
    def __init__(self, config: OllamaConfig | None = None) -> None:
        cfg = config or OllamaConfig()

        # Rationale: allow overriding via environment without changing code.
        model_override = os.getenv("OLLAMA_MODEL")
        self._model = model_override if model_override else cfg.model

        self._host = ollama_host()

        # Rationale: surface the last failure reason to the UI for debugging.
        self._last_error: Optional[str] = None
        # Rationale: store num_ctx to pass via options when set.
        self._num_ctx: Optional[int] = cfg.num_ctx

    @property
    def model(self) -> str:
        return self._model

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def chat(
        self,
        messages: List[ChatMessage],
        *,
        format: Optional[Any] = None,
        options_override: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Call the local Ollama chat API.

        Uses the Ollama Python library interface documented on Ollama model pages.
        Example usage shown for `from ollama import chat ...`. [src]
        - https://ollama.com/MedAIBase/MedGemma1.5
        """

        try:
            from ollama import Client
        except Exception:
            # Rationale: if the Python client isn't installed, the app should still run
            # with deterministic fallback explanations.
            self._last_error = "Python package 'ollama' is not available in this environment"
            return None

        try:
            self._last_error = None
            self._last_finish_reason = None
            self._last_note = None
            # Rationale: use an explicit client so we can control the host used for
            # connectivity debugging. Allow up to 10 minutes for long-running
            # local model calls before treating them as timeouts.
            client = Client(host=self._host, timeout=600.0)
            # Ollama supports passing generation parameters via `options` (e.g., temperature). [src]
            # - https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
            chat_options: Dict[str, Any] = {
                "temperature": DEFAULT_TEMPERATURE,
                "num_predict": 128,
            }
            if self._num_ctx is not None:
                chat_options["num_ctx"] = int(self._num_ctx)

            if options_override:
                # Rationale: allow per-call overrides (e.g., higher num_predict for long JSON).
                chat_options.update(options_override)

            # Rationale: Ollama supports structured outputs via the `format` parameter
            # (either `json` or a JSON schema). [src]
            # - https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
            try:
                if format is not None:
                    response = client.chat(
                        model=self._model,
                        messages=messages,
                        options=chat_options,
                        format=format,
                    )
                else:
                    response = client.chat(
                        model=self._model,
                        messages=messages,
                        options=chat_options,
                    )
            except TypeError:
                # Rationale: older ollama-python client versions may not accept `format`.
                response = client.chat(
                    model=self._model,
                    messages=messages,
                    options=chat_options,
                )
            # Rationale: ollama-python supports both dict-style and object-style
            # access for responses. [src]
            # - https://raw.githubusercontent.com/ollama/ollama-python/main/README.md
            if response is None:
                self._last_error = "Ollama returned no response"
                return None
            done_reason = (
                response.get("done_reason") if isinstance(response, dict) else getattr(response, "done_reason", None)
            )
            self._last_finish_reason = str(done_reason) if done_reason else None

            if hasattr(response, "message") and getattr(response, "message") is not None:
                content = getattr(response, "message").content
                if not content:
                    self._last_error = "Ollama returned an empty message content"
                    return None
                # Rationale: with structured outputs (`format`), `content` may already be
                # a Python list/dict. Downstream callers (e.g. LLM screening) expect a
                # JSON string, so we serialize non‑string content here instead of using
                # str(content), which would not be valid JSON. [src]
                if not isinstance(content, str):
                    try:
                        return json.dumps(content, ensure_ascii=False)
                    except TypeError:
                        return str(content)
                return content

            if isinstance(response, dict):
                msg = response.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if not content:
                        self._last_error = "Ollama returned an empty message content"
                        return None
                    # See rationale above: ensure non‑string structured content is
                    # serialized as proper JSON so parsers can consume it safely.
                    if not isinstance(content, str):
                        try:
                            return json.dumps(content, ensure_ascii=False)
                        except TypeError:
                            return str(content)
                    return content

            self._last_error = f"Unrecognized ollama response type: {type(response)}"
            return None
        except Exception as e:
            # Rationale: local model may not be pulled/served yet; we degrade gracefully.
            self._last_error = f"Ollama call failed: {type(e).__name__}: {_hide_address(str(e), self._host)}"
            return None


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


class OpenAICompatClient(_ReplyState):
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
        self._last_error: Optional[str] = None
        self._last_usage: Optional[Dict[str, Any]] = None

    @property
    def model(self) -> str:
        return self._resolved_model or self._configured_model or "(server default)"

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def last_usage(self) -> Optional[Dict[str, Any]]:
        """The usage the server reported for the last reply (tokens, and cost when it sends one)."""
        return self._last_usage

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
    ) -> Optional[str]:
        try:
            import requests
        except Exception:
            self._last_error = "Python package 'requests' is not available in this environment"
            return None

        try:
            self._last_error = None
            self._last_finish_reason = None
            self._last_note = None
            self._last_usage = None
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
                self._last_note = (
                    f"The server refused the answer format (HTTP {resp.status_code}), "
                    "so the model was asked again without it."
                )
                body.pop("response_format")
                resp = requests.post(url, json=body, headers=self._headers(), timeout=self._timeout_s)
            resp.raise_for_status()

            reply = resp.json()
            self._last_usage = reply.get("usage")
            choices = reply.get("choices") or []
            choice = choices[0] if choices else {}
            self._last_finish_reason = choice.get("finish_reason")
            content = _text_of((choice.get("message") or {}).get("content"))
            if not content:
                self._last_error = "Model server returned an empty message content"
                return None
            return content
        except Exception as e:
            self._last_error = f"Model server call failed: {type(e).__name__}: {_hide_address(str(e), self._base_url)}"
            return None
