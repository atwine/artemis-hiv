"""A limit on repeated visit checks (owner, 2026-11-26: at most 6 a minute, ACCESS.md section 6).

Each check can call the paid AI, so a page stuck in a loop must stop within a minute. Kept in
memory: one local user, one server; a restart starts the count again.
"""

from __future__ import annotations

import math
import threading
from collections import deque
from typing import Callable, Deque, Optional


class SlidingWindow:
    """At most `limit` uses in any `window` seconds."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float]) -> None:
        if limit < 1:
            raise ValueError(f"a limit of {limit} would refuse every use; it must be at least 1")
        self._limit = limit
        self._window = window
        self._clock = clock
        self._uses: Deque[float] = deque()
        self._lock = threading.Lock()  # the routes run in a thread pool

    def take(self) -> Optional[int]:
        """Use one if allowed and return None; otherwise the seconds to wait before the next."""
        with self._lock:
            now = self._clock()
            while self._uses and self._uses[0] <= now - self._window:
                self._uses.popleft()
            if len(self._uses) >= self._limit:
                return max(1, math.ceil(self._uses[0] + self._window - now))
            self._uses.append(now)
            return None
