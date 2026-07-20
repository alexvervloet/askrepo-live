# Plan: phases and definitions of done

Every phase ends with something checkable: a passing run, a filled table, a
public URL. Not a feeling. Gotchas go in the log at the bottom the moment they
surprise you.

## Phase 0: plumbing (done when the keyless smoke passes)

- [x] `python check_setup.py` all green
- [x] `python -m pytest backend` green: healthz, corpus list, SSE stream shape
      (meta, then sources, then tokens, then done), unknown-repo 404,
      overlong-question 422
- [x] `curl -N` against `/api/ask` shows the mock answer streaming as SSE frames
- [x] `npm run dev` + backend: the browser UI streams the mock answer, shows
      the MOCK badge, sources render as GitHub deep links, Stop aborts
      mid-stream (verified in-browser 2026-07-17)
- [x] `npm run build` clean (tsc + vite)

## Phase 1: real pipeline (done when a real cited answer renders locally)

- [x] Add `pyproject.toml` to ask-my-repo so it installs as a package.
      Upstream [PR #1](https://github.com/alexvervloet/ask-my-repo/pull/1),
      which also adds `AMR_PREFER_LOCAL`, `complete_stream()`, `answer_stream()`
- [ ] Swap the requirements pin from the `packaging-and-streaming` branch to
      main once PR #1 merges
- [x] Local pgvector via Docker (`askrepo-live-pg` on :5434; rag-at-scale owns
      :5432); indexed with ask-my-repo's CLI, Voyage forced via
      `AMR_PREFER_LOCAL=0`
- [x] `RealProvider` wraps `answer_stream()` behind the same event interface as
      the mock. The plan suspected upstream would need a streaming variant, and
      it did.
- [x] Frontend renders real citations that deep-link to the right GitHub lines
      (verified in-browser 2026-07-17)
- [x] Corpus table (2026-07-17, voyage-3, 1024-d; answer end to end: 13.4s
      total for a 5-citation grounded answer via claude-opus-4-8):

| corpus | chunks | index time | embed cost ($) |
|---|---|---|---|
| ask-my-repo | 75 (11 files) | 1.4s | ~$0.0008 (~12.6k tokens) |
| (second repo TBD) | | | |

## Phase 2: guardrails (done when the abuse tests pass)

- [x] Per-IP rate limit: hand-rolled token bucket, not slowapi. Why: the
      mechanism is about thirty lines, wants an injectable clock for tests,
      and sits in front of a streaming endpoint where slowapi's decorator
      model fits poorly. In-memory on purpose; the Postgres budget is the
      durable backstop.
- [x] Global daily budget cap in Postgres (`gateway_spend` ledger, rolling
      24 hours): per-answer token and dollar estimates from the real
      provider's `done` frame; once spent, the API answers with a friendly
      `error` frame and never calls the model. Verified live with
      `DAILY_BUDGET_USD=0.001`.
- [x] Per-IP daily question count from the same ledger. Question length was
      already capped in Phase 0.
- [x] Abuse tests: burst then 429s with `Retry-After`, per-IP isolation,
      refill behavior, IP daily cap, budget-exhausted frame. Rate limiting
      also verified live with curl (3x 200 then 429).
- [x] Chosen numbers (all env-overridable):

| knob | value | env var |
|---|---|---|
| burst per IP | 3 | `RATE_BURST` |
| sustained per IP | 5/min | `RATE_PER_MIN` |
| questions per IP | 25 per 24h | `IP_DAILY_LIMIT` |
| global model budget | $5.00 per 24h | `DAILY_BUDGET_USD` |
| question length | 500 chars | `MAX_QUESTION_CHARS` |

**Phase 2 complete.** First measured real answer: 1215 input tokens, 212
output tokens, ~$0.011 estimated.

## Phase 3: frontend polish (done when the demo GIF is in the README)

- [x] Regenerate button (re-runs the last asked question, not the edited
      textarea); error panel with `role="alert"`, parsed FastAPI detail, and a
      regenerate hint. Budget-exhausted will arrive as an `error` frame with a
      friendly message (Phase 2), which this panel renders as-is.
- [x] Answers render as markdown (react-markdown + remark-gfm). Real answers
      arrive with headings, code blocks, and tables; plain text was selling
      them short. Added beyond the original definition of done.
- [x] Mobile pass in code: theme-color metas, 44px touch targets, full-width
      buttons under 480px, long source paths wrap. Check on an actual phone
      before calling Phase 5 done.
- [x] MOCK badge only when provider=mock; real mode shows a small
      "retrieval + Claude · Ns" footer under the answer
- [x] Demo GIF in the README. Not hand-recorded: `npm run demo:gif`
      (Playwright + ffmpeg) is the browser-app analogue of the capstone's
      `demo.tape`. Scripted, reproducible, real app and real index, refuses to
      record mock. Also produces the 1280x640 social-preview card (repo
      Settings, then Social preview).

**Phase 3 complete.**

## Phase 4: containerize (done when the fresh-machine block works)

- [x] Multi-stage Dockerfile serves UI + API from one image. Three stages now:
      node build, a wheel stage (git is needed for the git-pinned ask-my-repo
      requirement and stays out of the runtime), python runtime with a
      healthcheck.
- [x] `docker compose up --build` runs app + pgvector end to end. Verified in
      CI on a fresh Ubuntu runner: healthz reports mock, the SSE stream
      delivers sources/token/done, the static UI serves. That is the
      fresh-machine proof, stronger than a run on my own laptop; the laptop
      run is blocked anyway (see gotcha log).
- [x] Copy-paste block in the README (Run it with Docker): keyless works with
      zero setup; real mode documents keys + the one-time index into the
      compose database on host port 5435.
- [x] Real-mode compose run, verified 2026-07-19 after local Docker recovered:
      indexed into the compose db (75 chunks), `secrun docker compose up`
      served a real cited answer through the container in 12.2s (~$0.011),
      and the spend row landed in the compose db's ledger.

**Phase 4 complete.**

## Phase 5: deploy (done when the public URL survives a week)

Prep done 2026-07-19: flyctl installed, `fly.toml` committed (always-on
shared-cpu-1x, 512MB, healthz check, ~$3-4/month). Runbook below; steps
marked [Alex] create accounts or cost money and are his to run.

- [x] [Alex] Fly.io account created and authenticated (2026-07-19)
- [x] [Alex] Neon account; project `lively-wind-97328969` in aws-us-west-2
      (the indexer creates the pgvector extension itself)
- [x] Fly app `askrepo-live` created; committed fly.toml used as-is
- [x] Secrets set from the Keychain via secrun plus the Neon DSN; nothing
      secret touched a file or the transcript
- [x] Indexed against Neon (75 chunks, same corpus and embedder as always)
- [x] `fly deploy --ha=false --local-only` (one machine, not the two-machine
      HA default). Public URL live 2026-07-19: healthz reports real; first
      public answer streamed 5 cited sources in 10.8s (~$0.016); the rate
      limit holds against the public URL (3x 200 then 429s, keyed on the
      real client IP through Fly's proxy)
- [ ] [Alex] Uptime monitor (UptimeRobot free tier) on `/healthz`
- [x] Public URL in the README
- [ ] First-week table: uptime, requests, total dollars

| week of | uptime | questions | est. spend ($) | fly bill ($) |
|---|---|---|---|---|
| 2026-07-19 | | | | |

## Phase 6: observability (done when the dashboard shows a week of traffic)

- [ ] Langfuse trace per `/api/ask` (question, retrieval, tokens, cost,
      latency)
- [ ] Dashboard screenshot + link in README; note what the first week's trend
      showed

## Gotcha log

- **2026-07-17**: a marker streamed word-by-word (`[MOCK FALLBACK]`) never
  appears contiguously in the raw SSE body; each word is its own `token`
  frame. Anything that searches the stream (tests, log greps) must reassemble
  the token frames first, the way the frontend does.
- **2026-07-17**: index and query embeddings must come from the same model.
  ask-my-repo embeds queries local-first, so an index built with Voyage would
  be searched with LM Studio vectors whenever the local box is reachable.
  Silently wrong answers, no error. Hence upstream `AMR_PREFER_LOCAL=0`
  (forced in the Docker image) and the hard gate in `get_provider()`: real
  mode refuses to start unless the flag is set.
- **2026-07-17**: ask-my-repo's `Config` reads env at class-definition time
  (dataclass field defaults), so `AMR_*` vars must be set before the process
  starts. Setting them in code after import does nothing.
- **2026-07-18**: local Docker Desktop wedged itself: every daemon-initiated
  registry pull hangs (Docker Hub and ECR alike) while container NAT traffic
  and host curl work fine, and freshly installed binaries stall on first run
  too. Survived a hard restart of Docker Desktop; established binaries (gh,
  git, curl) unaffected. Looks machine-level, probably cleared by a reboot.
  Lesson: CI is the better venue for fresh-machine verification anyway; the
  compose e2e now runs on every push.
- **2026-07-18**: the cost estimate systematically undercounts. Adaptive
  thinking bills as output tokens that never appear in the text stream, and
  chars/4 is a rough tokenizer stand-in. Treat the ledger as a floor and set
  `DAILY_BUDGET_USD` with headroom; exact usage lives in the provider's
  billing console, and Langfuse (Phase 6) will narrow the gap.
