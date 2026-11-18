"""LLM clients.

Two backends share one interface (`.model`, `.last_error`, `.chat(...)`):
- OllamaClient: a local Ollama server (the original setup).
- OpenAICompatClient: any OpenAI-compatible server, such as vLLM on a remote GPU.
  Selected by setting LLM_BASE_URL (see `openai_compat_config_from_env`).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, ClassVar, Dict, List, Optional, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


@dataclass(frozen=True)
class OllamaConfig:
    # Rationale: default to the locally pulled model tag to avoid mismatches.
    model: str = "aadide/medgemma-1.5-4b-it-Q4_K_S"
    # Rationale: allow setting the context window per request without changing server env.
    # Matches Ollama `num_ctx` parameter. [src]
    # - https://raw.githubusercontent.com/ollama/ollama/main/docs/modelfile.mdx#valid-parameters-and-values
    num_ctx: Optional[int] = None


class OllamaClient:
    def __init__(self, config: OllamaConfig | None = None) -> None:
        cfg = config or OllamaConfig()

        # Rationale: allow overriding via environment without changing code.
        model_override = os.getenv("OLLAMA_MODEL")
        self._model = model_override if model_override else cfg.model

        # Rationale: ollama-python allows a custom host via Client(host=...). [src]
        # - https://github.com/ollama/ollama-python#custom-client
        # Note: OLLAMA_HOST is sometimes set to a bind address like 0.0.0.0:11434;
        # clients cannot connect to 0.0.0.0, so we translate it to localhost. [src]
        # - https://github.com/ollama/ollama-python/issues/407
        raw_host = (os.getenv("OLLAMA_HOST") or "").strip()
        if raw_host:
            host = raw_host
            if "://" not in host:
                host = f"http://{host}"
            host = host.replace("http://0.0.0.0", "http://localhost").replace(
                "https://0.0.0.0", "http://localhost"
            )
            self._host = host
        else:
            self._host = "http://localhost:11434"

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
            # Rationale: use an explicit client so we can control the host used for
            # connectivity debugging. Allow up to 5 minutes for long-running
            # local model calls before treating them as timeouts.
            client = Client(host=self._host, timeout=600.0)
            # Rationale: keep outputs more deterministic for clinical UX.
            # Ollama supports passing generation parameters via `options` (e.g., temperature). [src]
            # - https://raw.githubusercontent.com/ollama/ollama/main/docs/api.md
            chat_options: Dict[str, Any] = {
                "temperature": 0.2,
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
            self._last_error = f"Ollama call failed (host={self._host}): {type(e).__name__}: {e}"
            return None


@dataclass(frozen=True)
class OpenAICompatConfig:
    # Example: http://<vllm-host>:8000/v1 (the path up to and including /v1).
    base_url: str
    # None means "use the first model the server lists".
    model: Optional[str] = None
    api_key: Optional[str] = None
    timeout_s: float = 600.0


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
        self._last_error: Optional[str] = None

    @property
    def model(self) -> str:
        return self._resolved_model or self._configured_model or "(server default)"

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

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
        if not models:
            raise RuntimeError(f"No models listed at {self._base_url}/models")
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
            options: Dict[str, Any] = {"temperature": 0.2, "num_predict": 128}
            if options_override:
                options.update(options_override)

            body: Dict[str, Any] = {"model": self._resolve_model(), "messages": list(messages)}
            for src, dst in self._OPTION_MAP.items():
                if options.get(src) is not None:
                    body[dst] = options[src]
            response_format = self._response_format(format)
            if response_format is not None:
                body["response_format"] = response_format

            url = f"{self._base_url}/chat/completions"
            resp = requests.post(url, json=body, headers=self._headers(), timeout=self._timeout_s)
            if resp.status_code == 400 and "response_format" in body:
                # Some servers reject schema-constrained output; the pipeline's JSON
                # parsers already cope with free-text JSON, so retry without it.
                body.pop("response_format")
                resp = requests.post(url, json=body, headers=self._headers(), timeout=self._timeout_s)
            resp.raise_for_status()

            choices = resp.json().get("choices") or []
            content = (choices[0].get("message") or {}).get("content") if choices else None
            if not content:
                self._last_error = "Model server returned an empty message content"
                return None
            return content
        except Exception as e:
            self._last_error = f"Model server call failed ({self._base_url}): {type(e).__name__}: {e}"
            return None
