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
from _lib import cwd_from_hook, group_id, mcp_get, mcp_post, read_stdin_json


def _changed_files(repo: str) -> list[str]:
    """Files modified vs the index (git status --porcelain)."""
    try:
        out = subprocess.check_output(
            ["git", "-C", repo, "status", "--porcelain"],
            text=True, stderr=subprocess.DEVNULL,
        )
        paths = []
        for line in out.splitlines():
            status, _, rel = line.partition(" ")
            rel = rel.strip()
            if rel:
                paths.append(str(Path(repo) / rel))
        return paths
    except Exception:
        return []


def main() -> None:
    payload = read_stdin_json()
    repo    = cwd_from_hook(payload)
    gid     = group_id(repo)

    if mcp_get("/health") is None:
        sys.exit(0)

    for fp in _changed_files(repo):
        mcp_post("/reindex", {"group_id": gid, "file_path": fp})

    sys.exit(0)


if __name__ == "__main__":
    main()
