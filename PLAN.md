# Plan — phases and definitions of done

Every phase ends with something checkable — a passing run, a filled table, a
public URL — not a feeling. Gotchas go in the log at the bottom the moment they
surprise you.

## Phase 0 — plumbing (done when the keyless smoke passes)

- [x] `python check_setup.py` all green
- [x] `python -m pytest backend` green — healthz, corpus list, SSE stream
      shape (meta → sources → token… → done), unknown-repo 404, overlong-question 422
- [x] `curl -N` against `/api/ask` shows the mock answer streaming as SSE frames
- [x] `npm run dev` + backend: the browser UI streams the mock answer, shows
      the MOCK badge, sources render as GitHub deep links, Stop aborts
      mid-stream (verified in-browser 2026-07-17)
- [x] `npm run build` clean (tsc + vite)

## Phase 1 — real pipeline (done when a real cited answer renders locally)

- [x] Add `pyproject.toml` to ask-my-repo so it installs as a package —
      upstream [PR #1](https://github.com/alexvervloet/ask-my-repo/pull/1),
      which also adds `AMR_PREFER_LOCAL`, `complete_stream()`, `answer_stream()`
- [ ] Swap the requirements pin from the `packaging-and-streaming` branch to
      main once PR #1 merges
- [x] Local pgvector via Docker (`askrepo-live-pg` on :5434; rag-at-scale owns
      :5432); indexed with ask-my-repo's CLI, Voyage forced via
      `AMR_PREFER_LOCAL=0`
- [x] `RealProvider` wraps `answer_stream()` behind the same event interface as
      the mock — the suspected upstream streaming variant was indeed needed
- [x] Frontend renders real citations that deep-link to the right GitHub lines
      (verified in-browser 2026-07-17)
- [x] Corpus table (2026-07-17, voyage-3, 1024-d; answer e2e: 13.4s total for
      a 5-citation grounded answer via claude-opus-4-8):

| corpus | chunks | index time | embed cost ($) |
|---|---|---|---|
| ask-my-repo | 75 (11 files) | 1.4s | ~$0.0008 (~12.6k tokens) |
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
- **2026-07-17** — **index and query embeddings must come from the same
  model.** ask-my-repo embeds queries local-first, so an index built with
  Voyage would be searched with LM Studio vectors whenever the local box is
  reachable — silently wrong answers, no error. Hence upstream
  `AMR_PREFER_LOCAL=0` (forced in the Docker image) and the hard gate in
  `get_provider()`: real mode refuses to start unless the flag is set.
- **2026-07-17** — ask-my-repo's `Config` reads env at class-definition time
  (dataclass field defaults), so `AMR_*` vars must be set before the process
  starts / the module imports — setting them in code after import does nothing.
