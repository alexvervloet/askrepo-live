"""The only module that talks to a model.

A provider yields (event, data) pairs matching the wire protocol in the
README: "sources" once, "token" repeatedly, "done" once. The real provider
wraps ask-my-repo (pgvector retrieve, then a streamed grounded answer); the
mock keeps the whole path exercisable keyless.
"""

import asyncio
import time
from typing import Any, AsyncIterator

from . import config

Event = tuple[str, Any]

_MOCK_SOURCES = [
    {"path": "ask_my_repo/retrieval.py", "start_line": 12, "end_line": 48},
    {"path": "ask_my_repo/answer.py", "start_line": 1, "end_line": 33},
]

_MOCK_ANSWER = (
    "[MOCK FALLBACK] No model was called. You asked {repo}: “{question}” "
    "— and this canned reply is streaming word by word so the SSE plumbing, "
    "the abort button, and the sources panel can all be exercised without keys. "
    "The two sources shown are hard-coded but deep-link to real lines, so the "
    "citation rendering is honest even when the answer is not. When the real "
    "provider lands (PLAN.md, Phase 1) this text is replaced by a grounded "
    "answer with citations from pgvector retrieval."
)

_BANNER = """\
================================================================
  askrepo-live is running on the MOCK provider.
  Answers are canned; the streaming/SSE/UI wiring is real.
  Why: {reason}.
  Set PROVIDER_STRICT=1 to refuse to start in this state.
================================================================"""


class MockProvider:
    """Streams a canned answer so the whole path is exercisable keyless."""

    name = "mock"

    async def answer(self, question: str, repo: str) -> AsyncIterator[Event]:
        start = time.monotonic()
        yield "sources", _MOCK_SOURCES
        for word in _MOCK_ANSWER.format(question=question, repo=repo).split(" "):
            yield "token", {"text": word + " "}
            await asyncio.sleep(0.02)
        yield "done", {"elapsed_ms": int((time.monotonic() - start) * 1000)}


def _answer_stream(question: str):
    from ask_my_repo.answer import answer_stream

    return answer_stream(question, dsn=config.DATABASE_URL or None)


class RealProvider:
    """ask-my-repo behind the wire protocol: retrieve, then stream the answer.

    ask-my-repo's API is synchronous, so retrieval and each delta fetch run on
    worker threads to keep the event loop (and other streams) unblocked.
    """

    name = "real"

    async def answer(self, question: str, repo: str) -> AsyncIterator[Event]:
        start = time.monotonic()
        chunks, deltas = await asyncio.to_thread(_answer_stream, question)
        yield "sources", [
            {"path": c.path, "start_line": c.start_line, "end_line": c.end_line}
            for c in chunks
        ]
        while (delta := await asyncio.to_thread(next, deltas, None)) is not None:
            yield "token", {"text": delta}
        yield "done", {"elapsed_ms": int((time.monotonic() - start) * 1000)}


def _real_unavailable_reason() -> str | None:
    if not (config.ANTHROPIC_API_KEY and config.VOYAGE_API_KEY and config.DATABASE_URL):
        return "no ANTHROPIC_API_KEY / VOYAGE_API_KEY / DATABASE_URL configured"
    try:
        from ask_my_repo.config import CONFIG as amr_config
    except ImportError:
        return "ask-my-repo is not installed"
    if amr_config.prefer_local:
        # the index is built with Voyage embeddings; a local-first query would
        # search it with vectors from a different model's space
        return "AMR_PREFER_LOCAL must be 0 so query embeddings match the Voyage-built index"
    return None


def get_provider() -> MockProvider | RealProvider:
    reason = _real_unavailable_reason()
    if reason is None:
        return RealProvider()
    if config.PROVIDER_STRICT:
        raise RuntimeError(
            f"PROVIDER_STRICT=1 but the real provider is unavailable: {reason}"
        )
    print(_BANNER.format(reason=reason))
    return MockProvider()
