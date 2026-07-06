"""
Per-route MCP usage statistics.

Every MCP tool invocation is counted and the whole table is persisted to a
JSON file inside the ``.mcp_memory`` directory, so we can answer questions
like: which MCP routes are actually used, how often, and how many of the
registered routes have never been called.

Design constraints (mirrors tools/stats.py):
  - Best-effort: a stats failure must NEVER break a tool call.
  - Thread-safe: tools run in executor threads *and* the async loop.
  - Self-describing on disk: the file is a plain JSON dump of the counters.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import time
from pathlib import Path
from threading import Lock

log = logging.getLogger(__name__)

# Persistence target. Configurable so the container can point it at a mounted
# volume; defaults to a `.mcp_memory` directory under /data.
_MEMORY_DIR = Path(os.getenv("MCP_MEMORY_DIR", "/data/.mcp_memory"))
_MEMORY_FILE = _MEMORY_DIR / "route_stats.json"

_lock = Lock()
# route name -> {"calls", "errors", "first_used", "last_used"}
_routes: dict[str, dict] = {}
# every route registered at import time, even if never called
_registered: set[str] = set()
_loaded = False


def _now_ms() -> int:
    return int(time.time() * 1000)


def _load_locked() -> None:
    """Load counters from disk once. Caller must hold _lock."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        raw = json.loads(_MEMORY_FILE.read_text())
        for name, rec in raw.get("routes", {}).items():
            if isinstance(rec, dict):
                _routes[name] = rec
    except (OSError, ValueError):
        # Missing or corrupt file — start fresh, nothing to recover.
        pass


def _flush_locked() -> None:
    """Atomically write counters to disk. Caller must hold _lock."""
    payload = {
        "updated_at": _now_ms(),
        "registered_routes": len(_registered | set(_routes)),
        "routes": _routes,
    }
    try:
        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _MEMORY_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True))
        os.replace(tmp, _MEMORY_FILE)
    except OSError as exc:
        log.debug("route stats flush skipped: %s", exc)


def register(name: str) -> None:
    """Mark a route as known (declared) without counting a call."""
    with _lock:
        _registered.add(name)


def record(name: str, ok: bool = True) -> None:
    """Count one invocation of *name*. Never raises."""
    try:
        now = _now_ms()
        with _lock:
            _load_locked()
            rec = _routes.setdefault(
                name, {"calls": 0, "errors": 0, "first_used": now, "last_used": now}
            )
            rec["calls"] += 1
            if not ok:
                rec["errors"] += 1
            rec["last_used"] = now
            _registered.add(name)
            _flush_locked()
    except Exception as exc:  # pragma: no cover - defensive
        log.debug("route stats record skipped: %s", exc)


def track(func):
    """Decorator: register the route and count every (async) invocation."""
    name = func.__name__
    register(name)

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        ok = True
        try:
            return await func(*args, **kwargs)
        except Exception:
            ok = False
            raise
        finally:
            record(name, ok)

    return wrapper


def summary() -> dict:
    """Aggregate view: how many routes exist, how many are used, per-route counts."""
    with _lock:
        _load_locked()
        routes = {n: dict(v) for n, v in _routes.items()}
        registered = sorted(_registered | set(routes))
    used = sorted(n for n in registered if routes.get(n, {}).get("calls", 0) > 0)
    unused = sorted(set(registered) - set(used))
    return {
        "registered_routes": len(registered),
        "used_routes": len(used),
        "unused_routes": unused,
        "total_calls": sum(v.get("calls", 0) for v in routes.values()),
        "total_errors": sum(v.get("errors", 0) for v in routes.values()),
        "routes": dict(
            sorted(routes.items(), key=lambda kv: kv[1].get("calls", 0), reverse=True)
        ),
        "path": str(_MEMORY_FILE),
    }
