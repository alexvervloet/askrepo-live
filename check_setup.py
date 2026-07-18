#!/usr/bin/env python3
"""Verify the environment for askrepo-live. Makes no paid call. Phase 0 is
fully keyless (mock provider); real keys only matter from Phase 1 on."""

import shutil
import subprocess
import sys
from pathlib import Path

OK, BAD = "  \033[32m✓\033[0m", "  \033[31m✗\033[0m"
failures = 0


def check(label: str, ok: bool, fix: str = "") -> None:
    global failures
    print(f"{OK if ok else BAD} {label}" + ("" if ok else f"\n      fix: {fix}"))
    failures += 0 if ok else 1


print("askrepo-live setup check\n")

check(
    f"Python {sys.version_info.major}.{sys.version_info.minor} (need 3.11+)",
    sys.version_info >= (3, 11),
    "install a newer Python",
)

for pkg in ("fastapi", "uvicorn", "httpx", "pytest"):
    try:
        __import__(pkg)
        check(f"package: {pkg}", True)
    except ImportError:
        check(f"package: {pkg}", False, "pip install -r backend/requirements.txt")

node = shutil.which("node")
check("node on PATH", node is not None, "install Node 20+ (nodejs.org or brew)")
if node:
    version = subprocess.run(["node", "-v"], capture_output=True, text=True).stdout.strip()
    major = int(version.lstrip("v").split(".")[0])
    check(f"node {version} (need 20+)", major >= 20, "upgrade Node")

check("npm on PATH", shutil.which("npm") is not None, "comes with Node")

root = Path(__file__).parent
check(
    "frontend dependencies installed",
    (root / "frontend" / "node_modules").is_dir(),
    "cd frontend && npm install",
)

sys.path.insert(0, str(root / "backend"))
from askrepo_live import config  # noqa: E402

real_ready = bool(config.ANTHROPIC_API_KEY and config.VOYAGE_API_KEY and config.DATABASE_URL)
check(
    f"provider: {'real (keys + DB set)' if real_ready else 'mock (keyless, fine for Phase 0)'}",
    True,
)

print()
if failures:
    print(f"{failures} check(s) failed")
    sys.exit(1)
print("all good")
