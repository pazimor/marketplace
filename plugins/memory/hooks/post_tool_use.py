#!/usr/bin/env python3
"""
PostToolUse hook — fires after Write / Edit / MultiEdit.
1. Re-index the modified file (hash-gated, only re-embeds changed symbols).
2. Log the change to session.log (read by haiku at Stop).
3. Mark the session dirty so the Stop hook knows to call haiku.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    append_session_log, cwd_from_hook, group_id, is_internal_session, mark_dirty,
    mcp_get, mcp_post, read_stdin_json,
)

# No-op for the headless haiku subprocess's own PostToolUse (see stop.py).
if is_internal_session():
    sys.exit(0)


def main() -> None:
    payload   = read_stdin_json()
    repo      = cwd_from_hook(payload)
    gid       = group_id(repo)
    tool_name = payload.get("tool_name", "")

    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    # Extract the file path — for all three tools (MultiEdit included) it
    # lives at the top level of tool_input, never inside edits[].
    tool_input = payload.get("tool_input") or {}
    fp = tool_input.get("file_path") or tool_input.get("path") or ""
    paths: list[str] = [fp] if fp else []

    now_ts = int(time.time())

    # Health check — if MCP is down, don't block
    if mcp_get("/health") is None:
        for fp in paths:
            if fp:
                append_session_log(repo, {"tool": tool_name, "path": fp, "ts": now_ts})
        mark_dirty(repo)
        sys.exit(0)

    for fp in paths:
        if fp:
            mcp_post("/reindex", {"group_id": gid, "file_path": fp})
            append_session_log(repo, {"tool": tool_name, "path": fp, "ts": now_ts})

    mark_dirty(repo)
    sys.exit(0)


if __name__ == "__main__":
    main()
