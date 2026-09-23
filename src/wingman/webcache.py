"""A small disk cache for Bright Data results.

Two problems it solves, both measured on a real run:
  - A live search took 45-100 seconds. Rehearsing a demo five times meant five
    waits and five times the credits, for identical results.
  - Bright Data credits are finite, and a hackathon budget is small.

Keyed on the tool name plus its arguments, so a repeated search or scrape is
served from disk. Entries expire (WINGMAN_WEB_CACHE_HOURS, default 12) so a
real run still sees today's web rather than yesterday's.
"""

import hashlib
import json
import time
from pathlib import Path

from wingman import config, events

CACHE_DIR = config.OUT_DIR / "cache" / "web"


def _key(tool: str, args: dict) -> str:
    """Stable filename for one call.

    sort_keys means {"query": "x"} hashes the same however the dict was built.
    Example: _key("search_engine", {"query": "Cognee"}) -> "search_engine-3f9a1c2b8d4e5f60"
    """
    blob = json.dumps({"tool": tool, "args": args}, sort_keys=True)
    return f"{tool}-{hashlib.sha256(blob.encode()).hexdigest()[:16]}"


def get(tool: str, args: dict) -> str | None:
    """A cached result, or None when absent, stale or unreadable."""
    if config.WEB_CACHE_HOURS <= 0:
        return None
    path = CACHE_DIR / f"{_key(tool, args)}.json"
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text())
    except Exception:
        # A truncated or hand-edited file is a miss, never an error.
        return None
    age_hours = (time.time() - entry.get("at", 0)) / 3600
    if age_hours > config.WEB_CACHE_HOURS:
        return None
    events.emit("tool", f"cache hit: {tool}", f"saved a live call, {age_hours:.1f}h old")
    return entry.get("text")


def put(tool: str, args: dict, text: str) -> None:
    """Store one result. Cache failures must never break a run."""
    if config.WEB_CACHE_HOURS <= 0:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{_key(tool, args)}.json").write_text(
            json.dumps({"at": time.time(), "tool": tool, "args": args, "text": text})
        )
    except OSError:
        pass


def clear() -> int:
    """Delete every cached result and return how many went. Used by `wingman reset`."""
    if not CACHE_DIR.exists():
        return 0
    files = list(CACHE_DIR.glob("*.json"))
    for path in files:
        path.unlink(missing_ok=True)
    return len(files)
