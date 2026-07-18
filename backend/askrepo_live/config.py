"""All configuration in one place, everything overridable by env var."""

import os

# The fixed corpus list. Adding a repo here (and indexing it) is the only way
# anything becomes askable; the public cannot trigger indexing.
CORPORA = {
    "ask-my-repo": {
        "github": "https://github.com/alexvervloet/ask-my-repo",
        "branch": "main",
    },
}

PROVIDER_STRICT = os.getenv("PROVIDER_STRICT", "") == "1"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Where the built frontend lives in the Docker image; empty in dev (Vite serves it).
STATIC_DIR = os.getenv("STATIC_DIR", "")

MAX_QUESTION_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "500"))

# Guardrails. Per-IP token bucket: allow a short burst, sustain RATE_PER_MIN
# requests per minute. The question cap and spend cap both cover a rolling
# 24 hours.
RATE_BURST = int(os.getenv("RATE_BURST", "3"))
RATE_PER_MIN = float(os.getenv("RATE_PER_MIN", "5"))
IP_DAILY_LIMIT = int(os.getenv("IP_DAILY_LIMIT", "25"))
DAILY_BUDGET_USD = float(os.getenv("DAILY_BUDGET_USD", "5.00"))

# Trust Fly-Client-IP / X-Forwarded-For only when a proxy we control sets them;
# trusting them on a directly-reachable server lets clients spoof their IP.
TRUST_PROXY = os.getenv("TRUST_PROXY", "") == "1"

# claude-opus-4-8 prices per 1M tokens, for the spend estimate. The estimate
# undercounts: adaptive thinking bills as output tokens that never appear in
# the text stream, and chars/4 is rough. Set the budget conservatively.
PRICE_IN_PER_MTOK = float(os.getenv("PRICE_IN_PER_MTOK", "5.00"))
PRICE_OUT_PER_MTOK = float(os.getenv("PRICE_OUT_PER_MTOK", "25.00"))
