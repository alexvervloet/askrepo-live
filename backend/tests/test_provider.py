"""Provider unit tests — no keys, no network, no database."""

import asyncio
from types import SimpleNamespace

from askrepo_live import provider


async def _collect(gen):
    return [event async for event in gen]


def test_real_provider_adapts_answer_stream_to_wire_events(monkeypatch):
    chunks = [
        SimpleNamespace(path="ask_my_repo/client.py", start_line=110, end_line=127),
        SimpleNamespace(path="ask_my_repo/answer.py", start_line=51, end_line=67),
    ]
    monkeypatch.setattr(
        provider, "_answer_stream", lambda q: (chunks, iter(["Hel", "lo."]))
    )

    events = asyncio.run(_collect(provider.RealProvider().answer("q", "ask-my-repo")))

    assert events[0][0] == "sources"
    assert events[0][1][0] == {
        "path": "ask_my_repo/client.py",
        "start_line": 110,
        "end_line": 127,
    }
    assert [d["text"] for e, d in events if e == "token"] == ["Hel", "lo."]
    assert events[-1][0] == "done"


def test_keyless_env_selects_mock():
    assert isinstance(provider.get_provider(), provider.MockProvider)


def test_keys_without_prefer_local_gate_still_degrade_to_mock(monkeypatch):
    # ask-my-repo is installed and AMR_PREFER_LOCAL is unset in tests, so the
    # embedding-space gate is the reason the real provider must be refused
    monkeypatch.setattr(provider.config, "ANTHROPIC_API_KEY", "k")
    monkeypatch.setattr(provider.config, "VOYAGE_API_KEY", "k")
    monkeypatch.setattr(provider.config, "DATABASE_URL", "postgresql://x")

    reason = provider._real_unavailable_reason()
    assert reason is not None and "AMR_PREFER_LOCAL" in reason
    assert isinstance(provider.get_provider(), provider.MockProvider)
