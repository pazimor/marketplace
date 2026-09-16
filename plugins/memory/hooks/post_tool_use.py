#!/usr/bin/env python3
"""
PostToolUse hook — fires after Write / Edit / MultiEdit.
1. Re-index the modified file (hash-gated, only re-embeds changed symbols).
2. Log the change to session.log (debug trail, rotated at SessionEnd).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    append_session_log, cwd_from_hook, group_id, is_internal_session,
    mcp_get, mcp_post, mem_is_remote, read_stdin_json, reindex_payload,
)

# No-op for the headless distiller subprocesses' own PostToolUse (see _distill.py).
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
        sys.exit(0)

    # A remote server can't open this file — send the content instead, keyed by
    # the repo-relative path so it merges with what the server's mirror indexed.
    remote = mem_is_remote()

    for fp in paths:
        if fp:
            if remote:
                body = reindex_payload(gid, repo, fp)
                if body:
                    mcp_post("/reindex", body)
            else:
                mcp_post("/reindex", {"group_id": gid, "file_path": fp})
            append_session_log(repo, {"tool": tool_name, "path": fp, "ts": now_ts})

    sys.exit(0)


if __name__ == "__main__":
    main()
