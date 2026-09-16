#!/usr/bin/env python3
"""
Enriched SessionStart bootstrap.

Prints a compact (~1-2k token) context block to stdout, which Claude Code
injects into the session: backlog state + recent memories + the 3-axes
reminder + identity to use for task_claim. Deterministic — one GET on the
memory MCP server, no LLM.

Runs concurrently with session_start.py (same plugin), which boots the
Docker stack — so we poll the server for a while instead of failing on the
first attempt (startup race), then degrade to the static reminder.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# This hook stays standalone (no _lib import): _lib imports httpx at module
# level, and bootstrap must still print the static reminder when httpx is
# missing. Hence the small duplication of the host/auth/TLS policy below —
# keep it in sync with _lib.
_MARKET_SETTINGS = Path.home() / ".config" / "market" / "settings.json"


def _settings() -> dict:
    try:
        return json.loads(_MARKET_SETTINGS.read_text())
    except Exception:
        return {}


MEM_HOST = os.getenv("MEM_HOST") or str(_settings().get("host") or "") or "127.0.0.1"
MEM_PORT = os.getenv("MEM_PORT", "7333")
MEM_URL = f"https://{MEM_HOST}:{MEM_PORT}"


def _mem_verify():
    if MEM_HOST in ("127.0.0.1", "localhost", "::1"):
        return False
    ca = os.getenv("MEM_CA_BUNDLE") or str(Path.home() / ".config" / "market" / "ca.pem")
    return ca if Path(ca).exists() else True


def _mem_headers() -> dict:
    tok = os.getenv("MEM_TOKEN") or str(_settings().get("token") or "")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


# No-op inside the headless haiku subprocess spawned by the memory plugin.
if os.getenv("MEM_HOOK_INTERNAL") == "1":
    sys.exit(0)


def _git(repo: str, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", repo, *args], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return ""


def group_id(repo: str) -> str:
    key = _git(repo, "remote", "get-url", "origin") or str(Path(repo).resolve())
    return hashlib.sha256(key.encode()).hexdigest()[:16]


MEMORY_WAIT_S = 25  # < the memory hook's own 30 s docker health wait

_INSTALLED_PLUGINS = Path.home() / ".claude" / "plugins" / "installed_plugins.json"


def memory_plugin_installed() -> bool:
    """True when the memory plugin (which boots the Docker stack) is installed."""
    try:
        plugins = json.loads(_INSTALLED_PLUGINS.read_text()).get("plugins", {})
        return any(name.split("@")[0] == "memory" and entries
                   for name, entries in plugins.items())
    except Exception:
        return False


def _try_fetch(gid: str) -> dict | None:
    try:
        import httpx  # optional — degrade gracefully if missing
        r = httpx.get(f"{MEM_URL}/bootstrap/{gid}", timeout=8.0,
                      verify=_mem_verify(), headers=_mem_headers())
        r.raise_for_status()
        data = r.json()
        return None if data.get("error") else data
    except Exception:
        return None


def fetch_bootstrap(gid: str) -> dict | None:
    """One attempt normally; when the memory plugin is installed its
    SessionStart is booting Docker in parallel, so retry until healthy."""
    data = _try_fetch(gid)
    if data is not None or not memory_plugin_installed():
        return data
    deadline = time.monotonic() + MEMORY_WAIT_S
    while time.monotonic() < deadline:
        time.sleep(1.0)
        data = _try_fetch(gid)
        if data is not None:
            return data
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        payload = {}
    repo = payload.get("cwd") or os.getcwd()
    gid = group_id(repo)
    branch = _git(repo, "branch", "--show-current") or "?"
    user = _git(repo, "config", "user.name") or os.getenv("USER", "unknown")
    worktree = str(Path(repo).resolve())

    lines: list[str] = [
        "## Project graph (memory + roadmap + code)",
        f"Identity for task_claim / roadmap_apply: user=`{user}`, worktree=`{worktree}`, branch=`{branch}`, group_id=`{gid}`.",
        "Usage rules (this project's graph — group_id above):",
        f"- Conceptual code question (\"where is X handled?\") → `code_search(group_id=\"{gid}\", query=…)` BEFORE Grep/Read. Grep stays right for literal/exhaustive sweeps.",
        f"- Architecture decision, refactor, or reopening a past choice → `memory_search(group_id=\"{gid}\", query=…)` REQUIRED before acting.",
        f"- Start of a non-trivial task → `graph_overview(group_id=\"{gid}\")` to orient.",
        "- Empty results are cheap and expected — call speculatively. "
        "Roadmap axis: backlog, roadmap_apply, task_claim; see the graph-usage skill.",
    ]

    data = fetch_bootstrap(gid)
    if data is None:
        if memory_plugin_installed():
            lines.append("_(memory server unreachable — backlog unavailable this session)_")
        else:
            lines.append("_(memory plugin not installed — backlog unavailable; "
                         "`market install` to enable the graph)_")
        print("\n".join(lines))
        return

    backlog = data.get("backlog", {})
    tasks = backlog.get("tasks", {})
    milestones = backlog.get("milestones", [])

    active = [m for m in milestones if m.get("status") == "active"]
    if active:
        lines.append("")
        lines.append("### Active milestones")
        for m in active:
            lines.append(f"- `{m['id']}` {m.get('title', '')} — {m.get('done', 0)}/{m.get('tasks', 0)} tasks done")

    def _fmt(t: dict) -> str:
        bits = []
        if t.get("claimed_by"):
            bits.append(f"claimed by {t['claimed_by']}")
        if t.get("blocked_reason"):
            bits.append(f"blocked: {t['blocked_reason']}")
        if t.get("depends_on"):
            bits.append("depends on " + ", ".join(t["depends_on"]))
        suffix = f" ({'; '.join(bits)})" if bits else ""
        return f"- `{t['id']}` {t.get('title', '')}{suffix}"

    for status, header in (("in_progress", "In progress"), ("blocked", "Blocked"), ("todo", "Todo")):
        items = tasks.get(status) or []
        if items:
            lines.append("")
            lines.append(f"### {header}")
            lines += [_fmt(t) for t in items[:8]]
            if len(items) > 8:
                lines.append(f"- … {len(items) - 8} more (call backlog)")

    ts = data.get("token_stats") or {}
    if ts.get("saved_tokens"):
        lines.append(
            f"_(code RAG so far: ~{ts['saved_tokens']:,} tokens saved over "
            f"{ts.get('search_calls', 0)} searches + {ts.get('fetch_calls', 0)} fetches"
            + (f", x{ts['ratio']} vs full reads" if ts.get("ratio") else "")
            + ")_"
        )

    memories = (data.get("overview") or {}).get("recent_memories") or []
    if memories:
        lines.append("")
        lines.append("### Recent memories")
        for m in memories[:5]:
            content = (m.get("content") or "").replace("\n", " ")[:160]
            lines.append(f"- [{m.get('type', 'fact')}] {content}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
    sys.exit(0)
