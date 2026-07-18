import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import budget, config
from .guardrails import RateLimiter, client_ip
from .provider import get_provider

log = logging.getLogger("askrepo_live")

app = FastAPI(title="askrepo-live")
provider = get_provider()
limiter = RateLimiter(burst=config.RATE_BURST, per_min=config.RATE_PER_MIN)

BUDGET_MESSAGE = (
    "This demo has spent its daily model budget. It frees up over the next "
    "24 hours; come back later."
)


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=config.MAX_QUESTION_CHARS)
    repo: str


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "provider": provider.name}


@app.get("/api/repos")
def repos() -> list[dict]:
    return [{"name": name, **meta} for name, meta in config.CORPORA.items()]


def _sse_response(gen) -> StreamingResponse:
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        # X-Accel-Buffering: proxies (Fly's, nginx) buffer streams unless told not to
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


@app.post("/api/ask")
async def ask(req: AskRequest, request: Request) -> StreamingResponse:
    if req.repo not in config.CORPORA:
        raise HTTPException(status_code=404, detail=f"unknown repo {req.repo!r}")

    ip = client_ip(request)
    allowed, retry_after = limiter.check(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )

    if provider.name == "real":
        if await asyncio.to_thread(budget.questions_today, ip) >= config.IP_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Daily question limit reached for your address. Come back tomorrow.",
            )
        if await asyncio.to_thread(budget.spent_today) >= config.DAILY_BUDGET_USD:

            async def exhausted():
                yield sse("meta", {"provider": provider.name, "repo": req.repo})
                yield sse("error", {"message": BUDGET_MESSAGE})

            return _sse_response(exhausted())

    async def stream():
        yield sse("meta", {"provider": provider.name, "repo": req.repo})
        done_data = None
        try:
            async for event, data in provider.answer(req.question, req.repo):
                if event == "done":
                    done_data = data
                yield sse(event, data)
        except Exception as exc:  # surface as a terminal frame, never a hung stream
            yield sse("error", {"message": str(exc)})
        if provider.name == "real" and done_data and "cost_usd_est" in done_data:
            try:
                await asyncio.to_thread(
                    budget.record,
                    ip,
                    len(req.question),
                    done_data["input_tokens_est"],
                    done_data["output_tokens_est"],
                    done_data["cost_usd_est"],
                )
            except Exception:  # a ledger write must never break a served answer
                log.exception("failed to record spend")

    return _sse_response(stream())


# In the Docker image the built frontend is served from here; in dev, Vite
# serves it and proxies /api. Mounted last so API routes win.
_static = (
    Path(config.STATIC_DIR)
    if config.STATIC_DIR
    else Path(__file__).resolve().parents[2] / "frontend" / "dist"
)
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
