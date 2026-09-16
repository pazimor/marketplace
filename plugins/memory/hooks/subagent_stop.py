#!/usr/bin/env python3
"""
SubagentStop hook — code-RAG reconcile only.

Sub-agent writes bypass PostToolUse (Claude Code issue #34692).
This hook catches them: diff against git to find modified files,
then re-indexes each one (hash-gated, zero LLM).

No haiku, no episodic memory write — that's the master's Stop hook.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (
    cwd_from_hook, group_id, is_internal_session, mcp_get, mcp_post, mem_is_remote,
    read_stdin_json,
)

# No-op for the headless distiller subprocesses' own SubagentStop (see _distill.py).
if is_internal_session():
    sys.exit(0)


def _changed_files(repo: str) -> list[str]:
    """Files modified vs the index (git status --porcelain)."""
    try:
        out = subprocess.check_output(
            ["git", "-C", repo, "status", "--porcelain"],
            text=True, stderr=subprocess.DEVNULL,
        )
        paths = []
        for line in out.splitlines():
            # Porcelain v1: two status columns + space + path. Don't split on
            # the first space — an unstaged status starts with one (" M foo").
            if len(line) < 4:
                continue
            rel = line[3:]
            # Renames/copies: "R  old -> new" — index the new path.
            if line[0] in "RC" and " -> " in rel:
                rel = rel.split(" -> ", 1)[1]
            rel = rel.strip().strip('"')
            if rel:
                paths.append(str(Path(repo) / rel))
        return paths
    except Exception:
        return []


def main() -> None:
    payload = read_stdin_json()
    repo    = cwd_from_hook(payload)
    gid     = group_id(repo)

    # Code-RAG reconcile only — pointless against a remote server, which cannot
    # read this machine's working tree.
    if mem_is_remote():
        sys.exit(0)

    if mcp_get("/health") is None:
        sys.exit(0)

    for fp in _changed_files(repo):
        mcp_post("/reindex", {"group_id": gid, "file_path": fp})

    sys.exit(0)


if __name__ == "__main__":
    main()
