# askrepo-live

The deployed face of [ask-my-repo](https://github.com/alexvervloet/ask-my-repo):
a streaming chat UI over a pre-indexed set of my repos, behind a FastAPI
gateway. Most portfolio AI projects only ever run on the author's laptop. This
one is built to run in public: rate limited, budget capped, observable, and
cheap enough to leave up.

![askrepo streaming a real cited answer about its own fallback code](assets/demo.gif)

> Tip: the recording is scripted and reproducible. `npm run demo:gif` (see the
> header of `frontend/scripts/record-demo.mjs`) drives the real app against the
> real index with Playwright and re-renders this GIF plus a 1280x640
> social-preview card. It refuses to record the mock provider.

## Architecture

```
browser (React + Vite, SSE over fetch)
   │
   ▼
FastAPI gateway
   ├─ per-IP rate limit + daily budget cap      (Phase 2)
   ├─ serves the built frontend in prod
   ├─ /healthz for uptime monitoring
   ▼
provider seam (the only place a model is called)
   ├─ mock: keyless, canned, loud               (always available)
   └─ real: ask-my-repo core                    (pgvector retrieve, then a
             streamed Claude answer,             Voyage embeddings)
             └─ Postgres + pgvector (Neon in prod)
```

Scope decision: visitors cannot index arbitrary repos. The demo serves a
fixed, pre-indexed corpus list. Letting the public start embedding jobs is an
unbounded cost, and the problem this project cares about is running retrieval
and generation safely in public, not accepting uploads.

## The wire protocol

`POST /api/ask` `{question, repo}` returns `text/event-stream`:

| event | data | meaning |
|---|---|---|
| `meta` | `{provider, repo}` | first frame; `provider` is `"mock"` or `"real"` |
| `sources` | `[{path, start_line, end_line}]` | retrieval results, sent before the answer |
| `token` | `{text}` | answer text, incrementally |
| `done` | `{elapsed_ms}` | stream finished cleanly |
| `error` | `{message}` | terminal; the stream ends after this |

The frontend streams with `fetch` and `ReadableStream` rather than
`EventSource`, because `EventSource` cannot POST a body.

Also: `GET /api/repos` (the corpus list), `GET /healthz`.

## Run it locally

```bash
# backend (terminal 1). Keyless: starts on the mock provider, loudly
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn askrepo_live.main:app --app-dir backend --reload

# frontend (terminal 2). Proxies /api to :8000
cd frontend && npm install && npm run dev
```

`python check_setup.py` verifies the environment. `python -m pytest backend`
runs the API tests. No keys, no network.

## Keyless mode

With no keys configured the gateway runs on a mock provider and says so
loudly: a banner at startup and a `[MOCK FALLBACK]` marker in every answer.
The streaming, the SSE protocol, and the UI wiring behave the same as in real
mode; only the text is canned. Set `PROVIDER_STRICT=1` to refuse to start in
that state instead. Same pattern as the deep-dive repos.

## Status

Phases 0, 1, and 3 are done: the real pipeline works end to end locally and
the UI is polished. Next is Phase 2, rate limiting and a daily budget cap,
which has to land before the public deploy. See [PLAN.md](PLAN.md) for the
phases and definitions of done. Deploy target is Fly.io + Neon Postgres
(Phase 5); the app is host-agnostic until then.
