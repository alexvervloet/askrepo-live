import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from .provider import get_provider

app = FastAPI(title="askrepo-live")
provider = get_provider()


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


@app.post("/api/ask")
def ask(req: AskRequest) -> StreamingResponse:
    if req.repo not in config.CORPORA:
        raise HTTPException(status_code=404, detail=f"unknown repo {req.repo!r}")

    async def stream():
        yield sse("meta", {"provider": provider.name, "repo": req.repo})
        try:
            async for event, data in provider.answer(req.question, req.repo):
                yield sse(event, data)
        except Exception as exc:  # surface as a terminal frame, never a hung stream
            yield sse("error", {"message": str(exc)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        # X-Accel-Buffering: proxies (Fly's, nginx) buffer streams unless told not to
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# In the Docker image the built frontend is served from here; in dev, Vite
# serves it and proxies /api. Mounted last so API routes win.
_static = (
    Path(config.STATIC_DIR)
    if config.STATIC_DIR
    else Path(__file__).resolve().parents[2] / "frontend" / "dist"
)
if _static.is_dir():
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")
