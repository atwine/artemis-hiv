"""LLM clients.

Two backends share one interface (`.model`, and `.chat(...)`, which returns a `ChatReply`: the
text with why it ended, any error, a note and the usage, all for that one call; plan item 4.6):
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


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None) -> None:
        cfg = config or OllamaConfig()

        # Rationale: allow overriding via environment without changing code.
        model_override = os.getenv("OLLAMA_MODEL")
        self._model = model_override if model_override else cfg.model

        self._host = ollama_host()

        # Rationale: store num_ctx to pass via options when set.
        self._num_ctx: Optional[int] = cfg.num_ctx

    @property
    def model(self) -> str:
        return self._model

    def chat(
        self,
        messages: List[ChatMessage],
        *,
        format: Optional[Any] = None,
        options_override: Optional[Dict[str, Any]] = None,
    ) -> ChatReply:
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
            return ChatReply(None, error="Python package 'ollama' is not available in this environment")

        try:
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
                return ChatReply(None, error="Ollama returned no response")
            done_reason = (
                response.get("done_reason") if isinstance(response, dict) else getattr(response, "done_reason", None)
            )
            finish = str(done_reason) if done_reason else None

            if hasattr(response, "message") and getattr(response, "message") is not None:
                content = getattr(response, "message").content
            elif isinstance(response, dict) and isinstance(response.get("message"), dict):
                content = response["message"].get("content")
            else:
                return ChatReply(None, finish_reason=finish, error=f"Unrecognized ollama response type: {type(response)}")
            if not content:
                return ChatReply(None, finish_reason=finish, error="Ollama returned an empty message content")
            # Rationale: with structured outputs (`format`), `content` may already be a Python
            # list/dict. Downstream callers (e.g. LLM screening) expect a JSON string, so non-string
            # content is serialized here instead of using str(content), which would not be valid JSON.
            if not isinstance(content, str):
                try:
                    content = json.dumps(content, ensure_ascii=False)
                except TypeError:
                    content = str(content)
            return ChatReply(content, finish_reason=finish)
        except Exception as e:
            # Rationale: local model may not be pulled/served yet; we degrade gracefully.
            return ChatReply(None, error=f"Ollama call failed: {type(e).__name__}: {_hide_address(str(e), self._host)}")


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
