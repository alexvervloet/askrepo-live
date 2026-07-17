# Plan — phases and definitions of done

Every phase ends with something checkable — a passing run, a filled table, a
public URL — not a feeling. Gotchas go in the log at the bottom the moment they
surprise you.

## Phase 0 — plumbing (done when the keyless smoke passes)

- [x] `python check_setup.py` all green
- [x] `python -m pytest backend` green — healthz, corpus list, SSE stream
      shape (meta → sources → token… → done), unknown-repo 404, overlong-question 422
- [x] `curl -N` against `/api/ask` shows the mock answer streaming as SSE frames
- [ ] `npm run dev` + backend: the browser UI streams the mock answer, shows
      the MOCK badge, sources render as GitHub deep links, Stop aborts mid-stream
- [x] `npm run build` clean (tsc + vite)

## Phase 1 — real pipeline (done when a real cited answer renders locally)

- [ ] Add `pyproject.toml` to ask-my-repo so it installs as a package
      (`pip install git+https://github.com/alexvervloet/ask-my-repo`) — small
      upstream PR to the flagship, its own lesson
- [ ] Local pgvector via Docker; index the demo corpora with ask-my-repo's CLI
- [ ] `RealProvider` wraps `retrieve()` + a **streaming** `answer()` behind the
      same event interface as the mock (upstream `answer.py` may need a
      streaming variant — verify live before assuming it's easy)
- [ ] Frontend renders real citations that deep-link to the right GitHub lines
- [ ] Fill the corpus table:

| corpus | chunks | index time | embed cost ($) |
|---|---|---|---|
| ask-my-repo | | | |
| (second repo TBD) | | | |

## Phase 2 — guardrails (done when the abuse tests pass)

- [ ] Per-IP rate limit (token bucket; slowapi or hand-rolled — decide and note why)
- [ ] Global **daily budget cap** persisted in Postgres: count tokens + $ per
      answer, hard-stop with a friendly `error` SSE event when the day's budget
      is spent
- [ ] Question length already capped (Phase 0); add per-IP daily question count
- [ ] Tests that hammer the API and assert 429s and the budget-exhausted event
- [ ] Record the chosen numbers here (req/min per IP, $/day cap, max question chars)

## Phase 3 — frontend polish (done when the demo GIF is in the README)

- [ ] Regenerate button; error and budget-exhausted states that don't look broken
- [ ] Mobile pass — this will be opened from a phone via a résumé link
- [ ] MOCK badge only when provider=mock; provider shown subtly when real
- [ ] Short screen-recording GIF in the README

## Phase 4 — containerize (done when the fresh-machine block works)

- [ ] Multi-stage Dockerfile (node build → python runtime) serves UI + API from
      one image
- [ ] `docker compose up` runs app + pgvector locally, end to end
- [ ] A copy-paste block in the README that works on a machine that isn't mine

## Phase 5 — deploy (done when the public URL survives a week)

- [ ] Neon Postgres (free tier, pgvector) + Fly.io smallest always-on VM —
      billing is a live decision, confirm before creating anything paid
- [ ] Secrets via `fly secrets set` fed from the Keychain (`secrun`), never files
- [ ] Index the corpora against Neon; uptime monitor on `/healthz`
- [ ] Public URL in the README + first-week table: uptime, requests, $ total

## Phase 6 — observability (done when the dashboard shows a week of traffic)

- [ ] Langfuse trace per `/api/ask` (question, retrieval, tokens, cost, latency)
- [ ] Dashboard screenshot + link in README; note what the first week's trend
      actually showed

## Gotcha log

- **2026-07-17** — a marker streamed word-by-word (`[MOCK FALLBACK]`) never
  appears contiguously in the raw SSE body; each word is its own `token` frame.
  Anything that searches the stream (tests, log greps) must reassemble the
  token frames first, the way the frontend does.
