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
   ├─ per-IP rate limit + daily budget cap
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
| `done` | `{elapsed_ms, ...}` | stream finished cleanly; real mode adds `input_tokens_est`, `output_tokens_est`, `cost_usd_est` |
| `error` | `{message}` | terminal; the stream ends after this |

The frontend streams with `fetch` and `ReadableStream` rather than
`EventSource`, because `EventSource` cannot POST a body.

Also: `GET /api/repos` (the corpus list), `GET /healthz`.

## Run it with Docker

Works on a machine that is not mine. Keyless gets you the full app on the
mock provider:

```bash
git clone https://github.com/alexvervloet/askrepo-live && cd askrepo-live
docker compose up --build
# open http://localhost:8080
```

Real mode needs keys and a one-time index of the corpus into the compose
database (host port 5435):

```bash
export ANTHROPIC_API_KEY=... VOYAGE_API_KEY=...   # or run through secrun
git clone https://github.com/alexvervloet/ask-my-repo /tmp/ask-my-repo
python -m venv /tmp/amr-venv && /tmp/amr-venv/bin/pip install "git+https://github.com/alexvervloet/ask-my-repo@packaging-and-streaming"
cd /tmp/ask-my-repo && AMR_PREFER_LOCAL=0 \
  AMR_DATABASE_URL=postgresql://postgres:pg@localhost:5435/postgres \
  /tmp/amr-venv/bin/ask-my-repo index .
cd - && docker compose up --build -d
```

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

## Guardrails

Strangers can hit this API, so it defends itself. Per IP: a burst of 3
requests, then 5 per minute, and at most 25 questions per rolling 24 hours.
Globally: a $5 daily model budget, tracked in a Postgres ledger with a cost
estimate per answer; once it is spent the API answers with a friendly `error`
frame instead of calling the model. Questions are capped at 500 characters,
and visitors cannot trigger indexing at all. Every knob is an env var (see
`backend/askrepo_live/config.py`). The cost estimate undercounts slightly
(thinking tokens are invisible to it), so the budget is set conservatively.

## Status

Phases 0 through 3 are done: the real pipeline works end to end locally, the
UI is polished, and the guardrails above are tested and verified live. Next
is Phase 4 (containerize) and Phase 5 (deploy). See [PLAN.md](PLAN.md) for
the phases and definitions of done. Deploy target is Fly.io + Neon Postgres;
the app is host-agnostic until then.
