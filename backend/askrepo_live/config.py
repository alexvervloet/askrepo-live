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
