"""Request-level guardrails: per-IP rate limiting and client IP resolution.

The daily budget lives in budget.py; question length is enforced by the
request model in main.py.
"""

import time
from typing import Callable

from fastapi import Request

from . import config


class RateLimiter:
    """Token bucket per client IP, in memory.

    In-memory is a deliberate choice: the deploy target is a single small VM,
    and the Postgres-backed daily budget is the real backstop, so a restart
    forgiving a recent burst costs nothing. Hand-rolled rather than slowapi:
    the mechanism is about thirty lines, needs an injectable clock to be
    testable, and has to sit in front of a streaming endpoint where slowapi's
    decorator model fits poorly.
    """

    def __init__(
        self, burst: int, per_min: float, clock: Callable[[], float] = time.monotonic
    ):
        self.burst = burst
        self.per_min = per_min
        self.clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_seen)

    def check(self, ip: str) -> tuple[bool, int]:
        """Try to consume one token. Returns (allowed, retry_after_seconds)."""
        now = self.clock()
        tokens, last = self._buckets.get(ip, (float(self.burst), now))
        tokens = min(float(self.burst), tokens + (now - last) * self.per_min / 60.0)
        if tokens >= 1.0:
            self._buckets[ip] = (tokens - 1.0, now)
            return True, 0
        self._buckets[ip] = (tokens, now)
        return False, int((1.0 - tokens) * 60.0 / self.per_min) + 1


def client_ip(request: Request) -> str:
    if config.TRUST_PROXY:
        ip = (
            request.headers.get("fly-client-ip")
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        )
        if ip:
            return ip
    return request.client.host if request.client else "unknown"
