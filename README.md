# askrepo-live

The deployed face of [ask-my-repo](https://github.com/alexvervloet/ask-my-repo):
a streaming chat UI over a pre-indexed set of my repos, behind a hardened
FastAPI gateway. The point of this project is the part most portfolios skip —
**an AI app strangers can actually hit**: rate-limited, budget-capped,
observable, and cheap enough to leave running.

## Architecture

```
browser — React + Vite, SSE over fetch
   │
   ▼
FastAPI gateway
   ├─ per-IP rate limit ─ daily budget cap        (Phase 2)
   ├─ serves the built frontend in prod
   ├─ /healthz for uptime monitoring
   ▼
provider seam (the only place a model is called)
   ├─ mock  — keyless, canned, LOUD               (Phase 0, always available)
   └─ real  — ask-my-repo core:                   (Phase 1)
              pgvector retrieve → Claude answer, Voyage embeddings
              └─ Postgres + pgvector (Neon in prod)
```

**Scope decision: you cannot index arbitrary repos.** The demo serves a fixed,
pre-indexed corpus list. Letting the public trigger embedding jobs is an
open-ended cost bomb; the interesting engineering here is running retrieval +
generation safely in public, not accepting uploads.

## The wire protocol

`POST /api/ask` `{question, repo}` returns `text/event-stream`:

| event | data | meaning |
|---|---|---|
| `meta` | `{provider, repo}` | first frame; `provider` is `"mock"` or `"real"` |
| `sources` | `[{path, start_line, end_line}]` | retrieval results, sent before the answer |
| `token` | `{text}` | answer text, incrementally |
| `done` | `{elapsed_ms}` | stream finished cleanly |
| `error` | `{message}` | terminal — the stream ends after this |

The frontend streams with `fetch` + `ReadableStream`, not `EventSource` —
`EventSource` can't POST a body.

Also: `GET /api/repos` (the corpus list), `GET /healthz`.

## Run it locally

```bash
# backend (terminal 1) — keyless: starts on the mock provider, loudly
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn askrepo_live.main:app --app-dir backend --reload

# frontend (terminal 2) — proxies /api to :8000
cd frontend && npm install && npm run dev
```

`python check_setup.py` verifies the environment. `python -m pytest backend`
runs the API tests — no keys, no network.

## Keyless mode

With no keys configured the gateway runs on a **mock provider** and says so
loudly: a banner at startup and a `[MOCK FALLBACK]` marker in every answer.
The streaming, SSE protocol, and UI wiring are real; the words are not. Set
`PROVIDER_STRICT=1` to refuse to start in that state instead. (Same pattern as
the deep-dive repos.)

## Status

Phase 0 (plumbing) — see [PLAN.md](PLAN.md) for the phases and definitions of
done. Deploy target is Fly.io + Neon Postgres (Phase 5); the app is
host-agnostic until then.
