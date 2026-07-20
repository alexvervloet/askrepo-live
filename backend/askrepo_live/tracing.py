"""Langfuse tracing, enabled only when LANGFUSE_* keys are configured.

One trace per /api/ask: a root span, a retriever child that ends when the
sources arrive, and the model call typed as a generation carrying token and
cost estimates so the dashboard can aggregate spend and latency. Keyless
(dev, CI, mock mode) every call here is a no-op; missing observability must
never take the product down, so failures degrade to logs, not errors.

Uses the explicit start_observation object API rather than the context-manager
one: the stream is an async generator, and context-var based "current spans"
can leak between interleaved requests.
"""

import logging
import os

log = logging.getLogger("askrepo_live")

_client = None


def init() -> None:
    global _client
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        log.info("langfuse: no keys configured, tracing disabled")
        return
    try:
        from langfuse import Langfuse

        client = Langfuse()  # reads LANGFUSE_PUBLIC_KEY / SECRET_KEY / HOST
        if not client.auth_check():
            log.error("langfuse: auth_check failed, tracing disabled")
            return
        _client = client
        log.info("langfuse: tracing enabled")
    except Exception:
        log.exception("langfuse: init failed, tracing disabled")


def _model_label(provider_name: str) -> str:
    if provider_name != "real":
        return provider_name
    try:
        from ask_my_repo.config import CONFIG

        return CONFIG.anthropic_model
    except Exception:
        return "unknown"


class AskTracer:
    """Collects one request's trace; every method is exception-proof."""

    def __init__(self, question: str, repo: str, provider_name: str, ip: str):
        self._root = None
        self._retrieval = None
        self._gen = None
        self._answer: list[str] = []
        self._question = question
        self._model = _model_label(provider_name)
        if _client is None:
            return
        try:
            self._root = _client.start_observation(
                name="ask",
                as_type="span",
                input=question,
                metadata={"repo": repo, "provider": provider_name, "ip": ip},
            )
            self._retrieval = self._root.start_observation(
                name="retrieval", as_type="retriever", input=question
            )
        except Exception:
            log.exception("langfuse: trace start failed")
            self._root = None

    def event(self, event: str, data) -> None:
        if self._root is None:
            return
        try:
            if event == "sources" and self._retrieval is not None:
                self._retrieval.update(output=data)
                self._retrieval.end()
                self._retrieval = None
                self._gen = self._root.start_observation(
                    name="answer",
                    as_type="generation",
                    model=self._model,
                    input=self._question,
                )
            elif event == "token":
                self._answer.append(data["text"])
            elif event == "done" and self._gen is not None:
                usage = {}
                if "input_tokens_est" in data:
                    usage = {
                        "input": data["input_tokens_est"],
                        "output": data["output_tokens_est"],
                    }
                self._gen.update(
                    output="".join(self._answer),
                    usage_details=usage or None,
                    cost_details=(
                        {"total": data["cost_usd_est"]}
                        if "cost_usd_est" in data
                        else None
                    ),
                )
        except Exception:
            log.exception("langfuse: event recording failed")

    def finish(self, error: str | None = None) -> None:
        if self._root is None:
            return
        try:
            if self._retrieval is not None:
                self._retrieval.end()
            if self._gen is not None:
                self._gen.end()
            if error is not None:
                self._root.update(level="ERROR", status_message=error, output=error)
            else:
                self._root.update(output="".join(self._answer))
            self._root.end()
        except Exception:
            log.exception("langfuse: trace finish failed")
