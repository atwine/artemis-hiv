"""Who may call the backend: ACCESS.md, in code. Every route goes through here.

There are no logins (ACCESS.md section 2), so a caller's role is where the request comes from:
- "rebinding": the Host isn't this laptop's name (a website using DNS rebinding);
- "website": the Origin is a web page other than the app's own;
- "local": anything else that reached 127.0.0.1 (the app's own pages, or a script).
"network" never gets here: the server listens on 127.0.0.1 only (backend/settings.py).

`AccessMiddleware` refuses every role but "local" before any route runs. `can()` is the
permission grid; each route also checks it (through `require`), so a route that doesn't
declare what it touches can't be added without a test failing (tests/test_access.py).
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional

from fastapi import HTTPException, Request
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.settings import Settings

# ACCESS.md section 3. A role, data kind or action missing here gets nothing.
GRID: Dict[str, Dict[str, FrozenSet[str]]] = {
    "local": {
        "patients": frozenset({"view"}),
        "visit_records": frozenset({"create"}),
        "guidelines": frozenset({"view"}),
    },
}


def can(role: str, action: str, data: str) -> bool:
    """One cell of the grid: may this role do this to this kind of data?"""
    return action in GRID.get(role, {}).get(data, frozenset())


def visible_patients(role: str, patients: List[Any]) -> List[Any]:
    """The patients this role may list: all of them for "local", none for anyone else."""
    return list(patients) if can(role, "view", "patients") else []


def _host_name(host: str) -> str:
    """"localhost:8000" -> "localhost"; "[::1]:8000" -> "::1"."""
    host = host.strip().lower()
    if host.startswith("["):
        return host[1:host.find("]")] if "]" in host else host
    return host.split(":", 1)[0]


def caller_role(*, host: Optional[str], origin: Optional[str], settings: Settings) -> str:
    if _host_name(host or "") not in settings.allowed_hosts:
        return "rebinding"
    if origin is not None and origin not in settings.allowed_origins:
        return "website"  # includes "Origin: null" from sandboxed frames and file:// pages
    return "local"


class AccessMiddleware:
    """Refuses (403) any request that isn't from "local", before routing, body parsing or CORS."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        role = caller_role(host=headers.get("host"), origin=headers.get("origin"), settings=self.settings)
        if role != "local":
            await JSONResponse({"detail": "Not allowed."}, status_code=403)(scope, receive, send)
            return
        scope.setdefault("state", {})["role"] = role
        await self.app(scope, receive, send)


def role_of(request: Request) -> str:
    return getattr(request.state, "role", "anonymous")


def require(data: str, action: str):
    """A route dependency: refuse (403) unless the caller's role may do `action` on `data`."""

    def check(request: Request) -> None:
        if not can(role_of(request), action, data):
            raise HTTPException(status_code=403, detail="Not allowed.")

    check.__name__ = f"require_{action}_{data}"
    return check
