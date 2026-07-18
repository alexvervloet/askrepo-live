"""Rate limiter unit tests with a fake clock. No network, no database."""

from askrepo_live.guardrails import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


def test_burst_allowed_then_denied_with_retry_after():
    rl = RateLimiter(burst=3, per_min=6, clock=FakeClock())
    assert all(rl.check("a")[0] for _ in range(3))
    allowed, retry_after = rl.check("a")
    assert not allowed
    assert retry_after >= 1


def test_tokens_refill_over_time():
    clock = FakeClock()
    rl = RateLimiter(burst=1, per_min=6, clock=clock)  # one token per 10s
    assert rl.check("a")[0]
    assert not rl.check("a")[0]
    clock.advance(10)
    assert rl.check("a")[0]


def test_refill_never_exceeds_burst():
    clock = FakeClock()
    rl = RateLimiter(burst=2, per_min=6, clock=clock)
    clock.advance(3600)
    assert rl.check("a")[0]
    assert rl.check("a")[0]
    assert not rl.check("a")[0]


def test_ips_are_independent():
    rl = RateLimiter(burst=1, per_min=6, clock=FakeClock())
    assert rl.check("a")[0]
    assert rl.check("b")[0]
    assert not rl.check("a")[0]
