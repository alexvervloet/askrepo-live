"""Abuse tests: hammer the API and assert the guardrails hold.

No keys, no network, no database; the budget checks are monkeypatched.
"""

import pytest
from fastapi.testclient import TestClient

from askrepo_live import main
from askrepo_live.guardrails import RateLimiter

client = TestClient(main.app)
BODY = {"question": "hi", "repo": "ask-my-repo"}


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    # keep tests independent of each other and of the module-level limiter
    monkeypatch.setattr(main, "limiter", RateLimiter(burst=100, per_min=6000))


def test_hammering_yields_429_with_retry_after(monkeypatch):
    frozen = lambda: 0.0  # nothing ever refills
    monkeypatch.setattr(main, "limiter", RateLimiter(burst=2, per_min=1, clock=frozen))

    codes = [client.post("/api/ask", json=BODY).status_code for _ in range(5)]
    assert codes[:2] == [200, 200]
    assert codes[2:] == [429, 429, 429]

    response = client.post("/api/ask", json=BODY)
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) >= 1
    assert "rate limit" in response.json()["detail"].lower()


def test_unknown_repo_does_not_consume_a_token(monkeypatch):
    monkeypatch.setattr(
        main, "limiter", RateLimiter(burst=1, per_min=1, clock=lambda: 0.0)
    )
    assert client.post("/api/ask", json={"question": "hi", "repo": "nope"}).status_code == 404
    assert client.post("/api/ask", json=BODY).status_code == 200


def test_ip_daily_cap_yields_429(monkeypatch):
    monkeypatch.setattr(main.provider, "name", "real", raising=False)
    monkeypatch.setattr(main.budget, "questions_today", lambda ip: 999)
    response = client.post("/api/ask", json=BODY)
    assert response.status_code == 429
    assert "limit" in response.json()["detail"].lower()


def test_budget_exhausted_is_a_friendly_error_frame(monkeypatch):
    monkeypatch.setattr(main.provider, "name", "real", raising=False)
    monkeypatch.setattr(main.budget, "questions_today", lambda ip: 0)
    monkeypatch.setattr(main.budget, "spent_today", lambda: 999.0)

    response = client.post("/api/ask", json=BODY)
    assert response.status_code == 200
    assert "event: error" in response.text
    assert "budget" in response.text.lower()
    assert "event: token" not in response.text  # no model call happened
