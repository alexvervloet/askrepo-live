"""The only module that talks to a model.

A provider yields (event, data) pairs matching the wire protocol in the
README: "sources" once, "token" repeatedly, "done" once. Phase 0 ships the
mock; the real provider (ask-my-repo's retrieve + a streaming answer behind
this same interface) lands in Phase 1 — see PLAN.md.
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


def get_provider() -> MockProvider:
    if config.ANTHROPIC_API_KEY and config.VOYAGE_API_KEY and config.DATABASE_URL:
        reason = "keys are set, but the real pipeline lands in Phase 1 (PLAN.md)"
    else:
        reason = "no ANTHROPIC_API_KEY / VOYAGE_API_KEY / DATABASE_URL configured"
    if config.PROVIDER_STRICT:
        raise RuntimeError(
            f"PROVIDER_STRICT=1 but the real provider is unavailable: {reason}"
        )
    print(_BANNER.format(reason=reason))
    return MockProvider()
