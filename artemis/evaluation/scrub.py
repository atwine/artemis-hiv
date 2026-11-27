"""Keeping the model server's address and this laptop's folder paths out of saved run files.

The repo is public, so every evaluation run is scrubbed before it's written. Moved out of
the old scripts/run_baseline.py (plan 4C.1), removed with Streamlit in 4C.6.
"""

from __future__ import annotations

import os
import re
from typing import Any, List

from artemis.ai.client import openai_compat_config_from_env
from artemis.config import PROJECT_ROOT

_ROOT_PREFIXES = sorted({str(PROJECT_ROOT) + os.sep, PROJECT_ROOT.as_posix() + "/"}, key=len, reverse=True)


def scrub(obj: Any, secrets: List[str]) -> Any:
    """`obj` with each of `secrets` replaced by "<model-server>" and the project folder's path removed."""
    if isinstance(obj, str):
        for s in secrets:
            obj = obj.replace(s, "<model-server>")
        for prefix in _ROOT_PREFIXES:
            obj = obj.replace(prefix, "")
        return obj
    if isinstance(obj, dict):
        return {k: scrub(v, secrets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v, secrets) for v in obj]
    return obj


def server_strings() -> List[str]:
    """The model server's address as it might appear in text: the URL, host:port and host, longest first."""
    cfg = openai_compat_config_from_env()
    if cfg is None:
        return []
    base = cfg.base_url.rstrip("/")
    host = re.sub(r"^https?://", "", base).split("/")[0]
    return sorted({base, host, host.split(":")[0]}, key=len, reverse=True)
