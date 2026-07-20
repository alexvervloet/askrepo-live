# LESSONS

Engineering lessons from taking a laptop RAG pipeline to a public URL: a
streaming React UI over a FastAPI gateway, rate limited, budget capped, and
traced. Most of these are about the gap between "works on my machine" and
"strangers can hit it": correctness bugs that only exist in production
topology, guardrails that have to assume abuse, and verification moving to
places my laptop cannot follow. Each lesson is tied to the concrete moment
that taught it. Running log, oldest first.

---

## 1. Test a stream the way its client consumes it

The first failing test of the project asserted that the mock answer contained
the marker `[MOCK FALLBACK]`. It never does: the mock streams word by word,
so `[MOCK` and `FALLBACK]` arrive in separate SSE token frames, and the
contiguous string does not exist anywhere in the raw response body. The fix
was to make the test reassemble the token frames exactly the way the frontend
does, and only then assert on the text.

Takeaway: anything that searches a streamed response (tests, log greps,
moderation hooks) must operate on the reassembled message, not the wire
bytes. If your test passes on the raw stream, it is probably asserting on
framing luck.

## 2. A graceful fallback on the embedding path is a silent correctness bug

ask-my-repo embeds queries local-first by design: try LM Studio, fall back to
Voyage. Great on a laptop, quietly catastrophic behind a deployed index. The
production index is built with Voyage vectors, so on any machine where LM
Studio happens to be reachable, queries would search that index with vectors
from a different model's space. No error, no empty result, just plausibly
wrong answers forever. The fix was an upstream `AMR_PREFER_LOCAL=0` flag,
baked into the Docker image, plus a hard gate in the provider: real mode
refuses to start unless the flag is set.

Takeaway: retrieval quality depends on the index and the query living in the
same embedding space, and nothing in the system will tell you when they
stop. Pin the embedder end to end and make the wrong configuration fail
loudly at startup, because it will never fail visibly at query time.

## 3. In a stream, fallback is only possible before the first token

Porting the local-then-foundation fallback to streaming forced a design
decision the non-streaming version never faced: once you have yielded tokens
to a caller, you cannot unsay them and restart on another model. The
implementation peeks at the first local delta before yielding anything; that
single `next()` call is the commit point. Succeed and the stream is local,
fail before it and the caller never knows, fail after it and the error
propagates honestly. Pleasingly, the first real answer the deployed app ever
served was the model explaining exactly this mechanism, with citations to
the lines that implement it.

Takeaway: streaming turns "retry on failure" into a one-way door. Decide
where your commit point is and make everything before it recoverable and
everything after it honest.

## 4. Degraded modes must announce themselves everywhere a human might look

The keyless mock mode says so in four places: a banner at startup, a
`[MOCK FALLBACK]` marker inside every answer, an amber badge in the UI, and
a demo recorder that flat refuses to record against the mock provider. That
last one mattered twice: a broken environment can never produce a
convincing-but-fake demo GIF, and reviewers of the recording can trust that
every citation in it is real.

Takeaway: a degraded mode that only logs its degradation will eventually be
mistaken for the real thing by someone who did not read the logs. Put the
announcement in the output itself, and teach your tooling to refuse work
that only makes sense against the real system.

## 5. Make the demo a build artifact, not a screen recording

`npm run demo:gif` drives the real app against the real index with
Playwright and renders the GIF plus a social-preview card. It got
re-recorded three times in two days (a tagline change, then a cost footer)
at the price of one command and a few cents each time; a hand-recorded GIF
would have gone stale on the first change. The recording script also
collected its own gotchas: Playwright's `recordVideo` needs Playwright's own
ffmpeg even when you use system Chrome; `<option>` elements inside a closed
`<select>` count as hidden to visibility waits; and a spawned server that
inherits stdio will wedge the calling pipeline if cleanup is ever skipped.

Takeaway: demo assets rot exactly as fast as the UI they show. Script the
recording like any other build output and regeneration becomes routine
instead of a chore you defer.

## 6. Layer your guardrails so each one can afford to be simple

The rate limiter is a thirty-line in-memory token bucket, hand-rolled
instead of slowapi because it needed an injectable clock for tests and had
to sit in front of a streaming endpoint. In-memory means a restart forgets
recent bursts, and that is fine, because the durable backstop lives a layer
down: a Postgres ledger that records every answer's estimated cost and
hard-stops the day at $5. The shallow layer is allowed to be simple and
forgetful precisely because the deep layer is neither.

Takeaway: not every guardrail needs to be durable, distributed, and exact.
Decide which layer carries the real safety property, make that one solid,
and let the outer layers be cheap.

## 7. A biased estimate is still a working guardrail if you know its direction

The per-answer cost estimate is chars/4 times list price, and it undercounts
by construction: adaptive thinking bills output tokens that never appear in
the text stream. That would be a fatal flaw in a billing system and is a
non-issue in a budget cap, because the bias direction is known and the cap
is set with headroom. Langfuse later closed the loop with real token counts
(first traced answer: 1268 in, 243 out, $0.0124, matching the estimate's
ballpark), which turns the known bias into a measured one.

Takeaway: before rejecting an estimate as inaccurate, ask what decision it
feeds. A spend cap needs the right order of magnitude and a known bias
direction, not four significant figures.

## 8. CI is the fresh machine your definition of done was talking about

Phase 4's definition of done was "a copy-paste block that works on a machine
that isn't mine". I spent hours trying to verify that locally through a
wedged Docker daemon before noticing the contradiction: my laptop is
precisely the machine the requirement excludes. A CI job that builds the
image and runs the whole compose stack keyless, then asserts the health
check, the SSE stream shape, and the served UI, passed on the first attempt
and now re-proves the fresh-machine story on every push.

Takeaway: when the requirement is "works somewhere clean", the verification
belongs in CI, not on the machine that has accumulated three years of state.
The local run is a convenience, not the proof.

## 9. When unrelated tools hang the same way, debug the layer they share

The Docker wedge ate a whole evening: daemon pulls hung, a freshly installed
Go binary hung, even reading a settings file stalled, while curl, git, and
gh worked fine. I restarted Docker three ways and side-loaded images before
stepping back and noticing the pattern pointed at the machine's network
stack, not at any one tool; the app's later deploy failure ("docker is
unavailable") turned out to be the same dropped connection. Docker pulls
worked again the next morning with no fix applied.

Takeaway: three different tools failing identically is one failure, not
three. Name the layer they share (network, DNS, disk, credentials) before
burning time inside any single tool, and remember that "transient" is a
real diagnosis.

## 10. Deploy tool defaults are policy decisions someone else made for you

Two Fly defaults would have silently changed the product: `fly deploy`
creates two machines for high availability (doubling the bill for a demo
that needs one), and autostop would put the machine to sleep between
visitors (turning the first impression into a cold start). One flag and one
config line fix both, but only if you read what the defaults do before
shipping them.

Takeaway: a deploy tool's defaults optimize for its vendor's median
customer, not for you. Read the generated config like a code review, and
price out what each default costs at your scale.

## 11. Deploying your own library is the sharpest review it will ever get

askrepo-live consumed ask-my-repo from the outside, and the first hour of
integration produced a four-commit upstream PR: the package was not
pip-installable (no pyproject.toml), had no streaming answer path, and had
no way to disable the local-first behavior a server cannot use. None of
these gaps were visible from inside the library's own repo, where the tests
import from the working tree and the CLI runs on the machine that has LM
Studio.

Takeaway: a library's real API surface is what an external consumer can
reach through packaging, and you only see it by becoming that consumer.
Ship one downstream user of your own code before calling the interface done.

## 12. In async servers, prefer explicit span objects over ambient context

The Langfuse SDK's ergonomic API (`start_as_current_observation`) tracks the
current span in context variables. Inside an async generator that suspends
on every SSE frame, two interleaved requests can stomp each other's
"current" span, so the gateway uses the explicit object API instead:
`start_observation`, hold the object, call `.end()`. The cost of leaving
the ergonomic path is that nothing is derived for you anymore; the trace
name and trace-level input/output each needed their own explicit call
(`propagate_attributes`, `set_trace_io`) that the context-manager path
would have handled implicitly.

Takeaway: ambient-context APIs are calibrated for straight-line sync code.
The moment your request interleaves, switch to explicit objects and expect
to hand-set whatever the ambient path used to infer.

## 13. Boring secret plumbing is a feature of everything built on top of it

Every secret in this project moved through exactly one channel: macOS
Keychain, injected per-command by a shell wrapper, forwarded to Fly with
`fly secrets set`, values never in files, never in the repo, never in the
transcript. Because the channel existed before the project did, adding
Voyage, the Neon DSN, and the Langfuse pair cost one line each and zero
thought, and there was never a moment where a key sat in a .env file
waiting to be committed.

Takeaway: decide the single path secrets take before the first one is
needed. Each new integration then inherits the discipline for free, and
the "temporary" plaintext key that ends up in git history simply has no
place to occur.
