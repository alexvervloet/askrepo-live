"""API smoke tests: no keys, no network, run against the mock provider."""

import json

from fastapi.testclient import TestClient

from askrepo_live.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["provider"] == "mock"


def test_repos_lists_the_fixed_corpora():
    r = client.get("/api/repos")
    assert r.status_code == 200
    names = [repo["name"] for repo in r.json()]
    assert "ask-my-repo" in names


def test_ask_streams_meta_sources_tokens_done_in_order():
    with client.stream(
        "POST", "/api/ask",
        json={"question": "How does retrieval work?", "repo": "ask-my-repo"},
    ) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    positions = [body.index(f"event: {e}") for e in ("meta", "sources", "token", "done")]
    assert positions == sorted(positions)
    assert "error" not in body
    # reassemble the token frames the way the frontend does
    answer = "".join(
        json.loads(frame.split("data: ", 1)[1])["text"]
        for frame in body.split("\n\n")
        if frame.startswith("event: token")
    )
    assert "[MOCK FALLBACK]" in answer  # keyless degradation must be loud


def test_unknown_repo_is_404():
    r = client.post("/api/ask", json={"question": "hi", "repo": "not-a-repo"})
    assert r.status_code == 404


def test_overlong_question_is_422():
    r = client.post("/api/ask", json={"question": "x" * 501, "repo": "ask-my-repo"})
    assert r.status_code == 422
