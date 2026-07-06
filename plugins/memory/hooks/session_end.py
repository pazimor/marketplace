#!/usr/bin/env python3
"""
SessionEnd hook — bookkeeping only.

Episodic memory is no longer written here: the session transcript is durable
on disk and will be distilled by the NEXT SessionStart (see _distill.py).
This hook just snapshots token stats and rotates the session log.

The Docker stack is intentionally NOT stopped here: it is shared by all
sessions on the machine, and stopping it would kill the MCP server out
from under any other live session.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    clear_session_log, cwd_from_hook, group_id, is_internal_session,
    mcp_get, read_stdin_json,
)

_STATS_KEYS = ("search_calls", "fetch_calls", "baseline_tokens",
               "actual_tokens", "saved_tokens")


def write_token_stats(repo: str, gid: str) -> None:
    """Snapshot the server's cumulative code-RAG token stats into
    .mcp-memory/token_stats.json (+ per-session delta and JSONL history).
    The server can't write here — the repo mount is read-only."""
    stats = mcp_get(f"/stats/{gid}")
    if not stats or stats.get("error"):
        return
    totals = {k: stats.get(k, 0) or 0 for k in _STATS_KEYS}
    totals["ratio"] = stats.get("ratio")

    out_file = Path(repo) / ".mcp-memory" / "token_stats.json"
    previous = {}
    try:
        previous = json.loads(out_file.read_text()).get("totals", {})
    except Exception:
        pass
    last_session = {k: totals[k] - (previous.get(k) or 0) for k in _STATS_KEYS}

    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(
        {"updated_at": now, "totals": totals, "last_session": last_session},
        indent=2,
    ) + "\n")
    if any(last_session.values()):
        with open(out_file.with_suffix(".log"), "a") as f:
            f.write(json.dumps({"at": now, **last_session}) + "\n")


# No-op for the headless distiller subprocesses' own SessionEnd.
if is_internal_session():
    sys.exit(0)


def main() -> None:
    payload = read_stdin_json()
    repo    = cwd_from_hook(payload)

    write_token_stats(repo, group_id(repo))
    clear_session_log(repo)
    sys.exit(0)


if __name__ == "__main__":
    main()
